"""World-related data models (Position, Tiles, Resources, Chunks, Stations)"""

from dataclasses import dataclass
from typing import Tuple, Optional, List, Dict
from enum import Enum
import math


@dataclass
class Position:
    """3D position in the world"""
    x: float
    y: float
    z: float = 0.0

    def distance_to(self, other: 'Position') -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2)

    def snap_to_grid(self) -> 'Position':
        return Position(int(self.x), int(self.y), int(self.z))

    def to_key(self) -> str:
        return f"{int(self.x)},{int(self.y)},{int(self.z)}"

    def copy(self) -> 'Position':
        return Position(self.x, self.y, self.z)


class TileType(Enum):
    """Types of terrain tiles"""
    GRASS = "grass"
    STONE = "stone"
    WATER = "water"
    DIRT = "dirt"


@dataclass
class WorldTile:
    """A single world tile"""
    position: Position
    tile_type: TileType
    occupied_by: Optional[str] = None
    ownership: Optional[str] = None
    walkable: bool = True

    def get_color(self) -> Tuple[int, int, int]:
        """Get display color for this tile - requires Config import at runtime"""
        # Import here to avoid circular dependency
        from core.config import Config
        return {
            TileType.GRASS: Config.COLOR_GRASS,
            TileType.STONE: Config.COLOR_STONE,
            TileType.WATER: Config.COLOR_WATER,
            TileType.DIRT: (139, 69, 19)
        }.get(self.tile_type, Config.COLOR_GRASS)


class ResourceType(Enum):
    """Types of harvestable resources"""
    OAK_TREE = "oak_tree"
    BIRCH_TREE = "birch_tree"
    MAPLE_TREE = "maple_tree"
    IRONWOOD_TREE = "ironwood_tree"
    COPPER_ORE = "copper_ore"
    IRON_ORE = "iron_ore"
    STEEL_ORE = "steel_ore"
    MITHRIL_ORE = "mithril_ore"
    LIMESTONE = "limestone"
    GRANITE = "granite"
    OBSIDIAN = "obsidian"
    STAR_CRYSTAL = "star_crystal"


RESOURCE_TIERS = {
    # Wood
    ResourceType.OAK_TREE: 1,
    ResourceType.BIRCH_TREE: 2,
    ResourceType.MAPLE_TREE: 2,
    ResourceType.IRONWOOD_TREE: 3,
    # Ore
    ResourceType.COPPER_ORE: 1,
    ResourceType.IRON_ORE: 1,
    ResourceType.STEEL_ORE: 2,
    ResourceType.MITHRIL_ORE: 2,
    # Stone
    ResourceType.LIMESTONE: 1,
    ResourceType.GRANITE: 1,
    ResourceType.OBSIDIAN: 3,
    ResourceType.STAR_CRYSTAL: 4
}


@dataclass
class LootDrop:
    """Loot drop definition"""
    item_id: str
    min_quantity: int
    max_quantity: int
    chance: float = 1.0


class ChunkType(Enum):
    """Types of world chunks"""
    PEACEFUL_FOREST = "peaceful_forest"
    PEACEFUL_QUARRY = "peaceful_quarry"
    PEACEFUL_CAVE = "peaceful_cave"
    DANGEROUS_FOREST = "dangerous_forest"
    DANGEROUS_QUARRY = "dangerous_quarry"
    DANGEROUS_CAVE = "dangerous_cave"
    RARE_HIDDEN_FOREST = "rare_hidden_forest"
    RARE_ANCIENT_QUARRY = "rare_ancient_quarry"
    RARE_DEEP_CAVE = "rare_deep_cave"


class StationType(Enum):
    """Types of crafting stations"""
    SMITHING = "smithing"
    ALCHEMY = "alchemy"
    REFINING = "refining"
    ENGINEERING = "engineering"
    ADORNMENTS = "adornments"


@dataclass
class CraftingStation:
    """A placed crafting station"""
    position: Position
    station_type: StationType
    tier: int

    def get_color(self) -> Tuple[int, int, int]:
        """Get display color for this station"""
        return {
            StationType.SMITHING: (180, 60, 60),
            StationType.ALCHEMY: (60, 180, 60),
            StationType.REFINING: (180, 120, 60),
            StationType.ENGINEERING: (60, 120, 180),
            StationType.ADORNMENTS: (180, 60, 180)
        }.get(self.station_type, (150, 150, 150))


class PlacedEntityType(Enum):
    """Types of placed entities"""
    TURRET = "turret"
    TRAP = "trap"
    BOMB = "bomb"
    UTILITY_DEVICE = "utility_device"
    CRAFTING_STATION = "crafting_station"
    TRAINING_DUMMY = "training_dummy"


@dataclass
class PlacedEntity:
    """A player-placed entity in the world (turret, trap, station, etc.)"""
    position: Position
    item_id: str  # Reference to item definition
    entity_type: PlacedEntityType
    tier: int = 1
    health: float = 100.0
    owner: Optional[str] = None
    # Turret-specific fields (legacy - prefer using tags)
    range: float = 5.0  # Detection/attack range
    damage: float = 20.0
    attack_speed: float = 1.0  # Attacks per second
    last_attack_time: float = 0.0
    target_enemy: Optional[any] = None  # Will be Enemy type
    # Tag system integration
    tags: List[str] = None  # Effect tags (fire, chain, burn, etc.)
    effect_params: Dict[str, any] = None  # Parameters for tag effects
    # Lifetime management
    lifetime: float = 300.0  # Total lifetime in seconds (5 minutes default)
    time_remaining: float = 300.0  # Time remaining before despawn

    def __post_init__(self):
        """Initialize mutable default values"""
        if self.tags is None:
            self.tags = []
        if self.effect_params is None:
            self.effect_params = {}

    def get_color(self) -> Tuple[int, int, int]:
        """Get display color for this entity"""
        return {
            PlacedEntityType.TURRET: (255, 140, 0),  # Dark orange
            PlacedEntityType.TRAP: (160, 82, 45),  # Sienna
            PlacedEntityType.BOMB: (178, 34, 34),  # Firebrick
            PlacedEntityType.UTILITY_DEVICE: (60, 180, 180),  # Cyan
            PlacedEntityType.CRAFTING_STATION: (105, 105, 105),  # Gray
            PlacedEntityType.TRAINING_DUMMY: (200, 200, 0)  # Yellow (visible target)
        }.get(self.entity_type, (150, 150, 150))

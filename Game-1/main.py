from __future__ import annotations
import pygame
import sys
import math
import random
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


# ============================================================================
# CONFIGURATION
# ============================================================================
class Config:
    # Window
    SCREEN_WIDTH = 1600
    SCREEN_HEIGHT = 900
    FPS = 60

    # World
    WORLD_SIZE = 100  # 100x100 grid
    CHUNK_SIZE = 16  # 16x16 tiles per chunk
    TILE_SIZE = 32  # Pixels per tile

    # UI Layout
    UI_PANEL_WIDTH = 400  # Right side for UI
    INVENTORY_PANEL_X = 0
    INVENTORY_PANEL_Y = 600
    INVENTORY_PANEL_WIDTH = 1200
    INVENTORY_PANEL_HEIGHT = 300
    INVENTORY_SLOT_SIZE = 50
    INVENTORY_SLOTS_PER_ROW = 10

    # Colors
    PLAYER_SPEED = 0.15  # Units per frame
    INTERACTION_RANGE = 3.0

    # Colors
    COLOR_BACKGROUND = (20, 20, 30)
    COLOR_GRID = (40, 40, 50)
    COLOR_GRASS = (34, 139, 34)
    COLOR_STONE = (128, 128, 128)
    COLOR_WATER = (30, 144, 255)
    COLOR_PLAYER = (255, 215, 0)
    COLOR_INTERACTION_RANGE = (255, 255, 0, 50)
    COLOR_UI_BG = (30, 30, 40)
    COLOR_TEXT = (255, 255, 255)
    COLOR_HEALTH = (255, 0, 0)
    COLOR_HEALTH_BG = (50, 50, 50)

    # Resource colors
    COLOR_TREE = (0, 100, 0)
    COLOR_ORE = (169, 169, 169)
    COLOR_STONE_NODE = (105, 105, 105)
    COLOR_HP_BAR = (0, 255, 0)
    COLOR_HP_BAR_BG = (100, 100, 100)

    # Feedback colors
    COLOR_DAMAGE_NORMAL = (255, 255, 255)
    COLOR_DAMAGE_CRIT = (255, 215, 0)

    # Inventory UI colors
    COLOR_SLOT_EMPTY = (40, 40, 50)
    COLOR_SLOT_FILLED = (50, 60, 70)
    COLOR_SLOT_BORDER = (100, 100, 120)
    COLOR_SLOT_SELECTED = (255, 215, 0)
    COLOR_TOOLTIP_BG = (20, 20, 30, 230)

    # Rarity colors
    RARITY_COLORS = {
        "common": (200, 200, 200),
        "uncommon": (30, 255, 0),
        "rare": (0, 112, 221),
        "epic": (163, 53, 238),
        "legendary": (255, 128, 0),
        "artifact": (230, 204, 128)
    }


# ============================================================================
# TRANSLATION SYSTEM (JSON-Driven Value Lookups)
# ============================================================================
class TranslationDatabase:
    """Loads and provides lookups for text-to-number translations"""
    _instance = None

    def __init__(self):
        self.magnitude_values = {}
        self.duration_seconds = {}
        self.mana_costs = {}
        self.cooldown_seconds = {}
        self.rarity_multipliers = {}
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TranslationDatabase()
        return cls._instance

    def load_from_files(self, base_path: str = ""):
        """Load all translation tables"""
        # Try to load skills-translation-table.JSON
        possible_paths = [
            f"{base_path}Definitions.JSON/skills-translation-table.JSON",
            f"{base_path}../Definitions.JSON/skills-translation-table.JSON",
            f"Game-1/Definitions.JSON/skills-translation-table.JSON",
        ]

        loaded = False
        for path in possible_paths:
            if Path(path).exists():
                self._load_translation_file(path)
                loaded = True
                print(f"✓ Loaded translation tables from {Path(path).name}")
                break

        if not loaded:
            print("⚠ Translation tables not found, using defaults")
            self._create_default_translations()

        self.loaded = True

    def _load_translation_file(self, filepath: str):
        """Load translation table from JSON"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Load magnitude values from base effects
            if 'BASE_EFFECT_TYPES' in data:
                # Need to load from skills-base-effects-1.JSON
                pass

            # Load durations
            if 'durationTranslations' in data:
                for key, val in data['durationTranslations'].items():
                    self.duration_seconds[key] = val.get('seconds', 0)

            # Load mana costs
            if 'manaCostTranslations' in data:
                for key, val in data['manaCostTranslations'].items():
                    self.mana_costs[key] = val.get('cost', 0)

            # Load cooldowns
            if 'cooldownTranslations' in data:
                for key, val in data['cooldownTranslations'].items():
                    self.cooldown_seconds[key] = val.get('seconds', 0)

            # Load skill progression
            if 'skillProgressionSystem' in data:
                self.skill_exp_requirements = data['skillProgressionSystem'].get('expRequirements', {})

            # Load rarity multipliers (might need separate file)
            self.rarity_multipliers = {
                'common': 1.0,
                'uncommon': 1.15,
                'rare': 1.35,
                'epic': 1.6,
                'legendary': 2.0,
                'mythic': 2.5
            }

        except Exception as e:
            print(f"⚠ Error loading translations: {e}")
            self._create_default_translations()

    def _create_default_translations(self):
        """Create default translation values"""
        # Magnitude values (from skills-base-effects-1.JSON)
        self.magnitude_values = {
            'minor': 0.5,
            'moderate': 1.0,
            'major': 2.0,
            'extreme': 4.0
        }

        # Duration
        self.duration_seconds = {
            'instant': 0,
            'brief': 15,
            'moderate': 30,
            'long': 60,
            'extended': 120
        }

        # Mana costs
        self.mana_costs = {
            'low': 30,
            'moderate': 60,
            'high': 100,
            'extreme': 150
        }

        # Cooldowns
        self.cooldown_seconds = {
            'short': 120,
            'moderate': 300,
            'long': 600,
            'extreme': 1200
        }

        # Rarity multipliers
        self.rarity_multipliers = {
            'common': 1.0,
            'uncommon': 1.15,
            'rare': 1.35,
            'epic': 1.6,
            'legendary': 2.0,
            'mythic': 2.5
        }

        # Skill EXP requirements (1000, 2000, 4000, 8000...)
        self.skill_exp_requirements = {
            'level1': 1000,
            'level2': 2000,
            'level3': 4000,
            'level4': 8000,
            'level5': 16000,
            'level6': 32000,
            'level7': 64000,
            'level8': 128000,
            'level9': 256000,
            'level10': 512000
        }

    def get_magnitude_value(self, magnitude: str) -> float:
        """Get numeric value for magnitude text"""
        return self.magnitude_values.get(magnitude, 1.0)

    def get_duration(self, duration: str) -> float:
        """Get seconds for duration text"""
        return self.duration_seconds.get(duration, 0)

    def get_mana_cost(self, cost: str) -> int:
        """Get mana cost for text"""
        return self.mana_costs.get(cost, 0)

    def get_cooldown(self, cooldown: str) -> float:
        """Get cooldown in seconds"""
        return self.cooldown_seconds.get(cooldown, 0)

    def get_rarity_multiplier(self, rarity: str) -> float:
        """Get multiplier for rarity"""
        return self.rarity_multipliers.get(rarity, 1.0)

    def get_skill_exp_for_level(self, level: int) -> int:
        """Get EXP required for skill level"""
        return self.skill_exp_requirements.get(f'level{level}', 1000)


# ============================================================================
# SKILL SYSTEM (JSON-Driven)
# ============================================================================
@dataclass
class MaterialDefinition:
    """Material definition loaded from JSON"""
    material_id: str
    name: str
    tier: int
    category: str
    rarity: str
    description: str = ""
    max_stack: int = 99
    properties: Dict = field(default_factory=dict)


class MaterialDatabase:
    """Global material database loaded from JSON"""
    _instance = None

    def __init__(self):
        self.materials: Dict[str, MaterialDefinition] = {}
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = MaterialDatabase()
        return cls._instance

    def load_from_file(self, filepath: str):
        """Load materials from JSON file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            materials_list = data.get('materials', [])

            for mat_data in materials_list:
                mat = MaterialDefinition(
                    material_id=mat_data.get('materialId', ''),
                    name=mat_data.get('name', ''),
                    tier=mat_data.get('tier', 1),
                    category=mat_data.get('category', 'unknown'),
                    rarity=mat_data.get('rarity', 'common'),
                    description=mat_data.get('description', ''),
                    max_stack=mat_data.get('maxStack', 99),
                    properties=mat_data.get('properties', {})
                )
                self.materials[mat.material_id] = mat

            self.loaded = True
            print(f"✓ Loaded {len(self.materials)} materials from JSON")
            return True

        except FileNotFoundError:
            print(f"⚠ Material file not found: {filepath}")
            print("  Creating placeholder materials...")
            self._create_placeholder_materials()
            return False
        except Exception as e:
            print(f"⚠ Error loading materials: {e}")
            print("  Creating placeholder materials...")
            self._create_placeholder_materials()
            return False

    def _create_placeholder_materials(self):
        """Create placeholder materials if JSON not found"""
        placeholder_materials = [
            ("oak_log", "Oak Log", 1, "wood", "common"),
            ("birch_log", "Birch Log", 2, "wood", "common"),
            ("maple_log", "Maple Log", 3, "wood", "uncommon"),
            ("ironwood_log", "Ironwood Log", 4, "wood", "rare"),
            ("copper_ore", "Copper Ore", 1, "ore", "common"),
            ("iron_ore", "Iron Ore", 2, "ore", "common"),
            ("steel_ore", "Steel Ore", 3, "ore", "uncommon"),
            ("mithril_ore", "Mithril Ore", 4, "ore", "rare"),
            ("limestone", "Limestone", 1, "stone", "common"),
            ("granite", "Granite", 2, "stone", "common"),
            ("obsidian", "Obsidian", 3, "stone", "uncommon"),
            ("star_crystal", "Star Crystal", 4, "stone", "legendary"),
        ]

        for mat_id, name, tier, category, rarity in placeholder_materials:
            self.materials[mat_id] = MaterialDefinition(
                material_id=mat_id,
                name=name,
                tier=tier,
                category=category,
                rarity=rarity,
                description=f"A {rarity} {category} material (Tier {tier})"
            )

        self.loaded = True
        print(f"✓ Created {len(self.materials)} placeholder materials")

    def get_material(self, material_id: str) -> Optional[MaterialDefinition]:
        """Get material definition by ID"""
        return self.materials.get(material_id)


# ============================================================================
# POSITION CLASS (3D-READY)
# ============================================================================
@dataclass
class Position:
    """3D position (z=0 for 2D, ready for 3D expansion)"""
    x: float
    y: float
    z: float = 0.0

    def distance_to(self, other: 'Position') -> float:
        """Euclidean distance (works in 2D when z=0, ready for 3D)"""
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )

    def snap_to_grid(self) -> 'Position':
        """Snap to integer coordinates for collision detection"""
        return Position(int(self.x), int(self.y), int(self.z))

    def to_key(self) -> str:
        """Convert to dictionary key"""
        return f"{int(self.x)},{int(self.y)},{int(self.z)}"

    def copy(self) -> 'Position':
        return Position(self.x, self.y, self.z)


# ============================================================================
# TILE SYSTEM
# ============================================================================
class TileType(Enum):
    GRASS = "grass"
    STONE = "stone"
    WATER = "water"
    DIRT = "dirt"


@dataclass
class WorldTile:
    position: Position
    tile_type: TileType
    occupied_by: Optional[str] = None
    ownership: Optional[str] = None
    walkable: bool = True

    def get_color(self) -> Tuple[int, int, int]:
        colors = {
            TileType.GRASS: Config.COLOR_GRASS,
            TileType.STONE: Config.COLOR_STONE,
            TileType.WATER: Config.COLOR_WATER,
            TileType.DIRT: (139, 69, 19)
        }
        return colors.get(self.tile_type, Config.COLOR_GRASS)


# ============================================================================
# CHUNK SYSTEM
# ============================================================================
class ChunkType(Enum):
    PEACEFUL_FOREST = "peaceful_forest"
    PEACEFUL_QUARRY = "peaceful_quarry"
    PEACEFUL_CAVE = "peaceful_cave"
    DANGEROUS_FOREST = "dangerous_forest"
    DANGEROUS_QUARRY = "dangerous_quarry"
    DANGEROUS_CAVE = "dangerous_cave"
    RARE_HIDDEN_FOREST = "rare_hidden_forest"
    RARE_ANCIENT_QUARRY = "rare_ancient_quarry"
    RARE_DEEP_CAVE = "rare_deep_cave"


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
        """Roll d10 to determine chunk type"""
        roll = random.randint(1, 10)

        if roll <= 5:  # Peaceful (50%)
            return random.choice([
                ChunkType.PEACEFUL_FOREST,
                ChunkType.PEACEFUL_QUARRY,
                ChunkType.PEACEFUL_CAVE
            ])
        elif roll <= 8:  # Dangerous (30%)
            return random.choice([
                ChunkType.DANGEROUS_FOREST,
                ChunkType.DANGEROUS_QUARRY,
                ChunkType.DANGEROUS_CAVE
            ])
        else:  # Rare (20%)
            return random.choice([
                ChunkType.RARE_HIDDEN_FOREST,
                ChunkType.RARE_ANCIENT_QUARRY,
                ChunkType.RARE_DEEP_CAVE
            ])

    def generate_tiles(self):
        """Generate tiles based on chunk type"""
        start_x = self.chunk_x * Config.CHUNK_SIZE
        start_y = self.chunk_y * Config.CHUNK_SIZE

        # Base tile type based on chunk theme
        base_tile = TileType.GRASS
        if "quarry" in self.chunk_type.value or "cave" in self.chunk_type.value:
            base_tile = TileType.STONE

        # Generate tiles
        for x in range(start_x, start_x + Config.CHUNK_SIZE):
            for y in range(start_y, start_y + Config.CHUNK_SIZE):
                pos = Position(x, y, 0)
                # Add some variation
                if random.random() < 0.1:
                    tile_type = TileType.DIRT
                else:
                    tile_type = base_tile

                self.tiles[pos.to_key()] = WorldTile(pos, tile_type)

    def spawn_resources(self):
        """Spawn resources based on chunk type"""
        start_x = self.chunk_x * Config.CHUNK_SIZE
        start_y = self.chunk_y * Config.CHUNK_SIZE

        # Determine resource counts based on chunk type
        if "peaceful" in self.chunk_type.value:
            resource_count = random.randint(3, 6)
            tier_range = (1, 2)  # T1-T2
        elif "dangerous" in self.chunk_type.value:
            resource_count = random.randint(5, 8)
            tier_range = (2, 3)  # T2-T3
        else:  # rare
            resource_count = random.randint(6, 10)
            tier_range = (3, 4)  # T3-T4

        # Spawn resources
        for _ in range(resource_count):
            # Random position in chunk
            x = start_x + random.randint(1, Config.CHUNK_SIZE - 2)
            y = start_y + random.randint(1, Config.CHUNK_SIZE - 2)
            pos = Position(x, y, 0)

            # Determine resource type based on chunk theme
            if "forest" in self.chunk_type.value:
                resource_types = [ResourceType.OAK_TREE, ResourceType.BIRCH_TREE,
                                  ResourceType.MAPLE_TREE, ResourceType.IRONWOOD_TREE]
            elif "quarry" in self.chunk_type.value:
                resource_types = [ResourceType.LIMESTONE, ResourceType.GRANITE,
                                  ResourceType.OBSIDIAN, ResourceType.STAR_CRYSTAL]
            else:  # cave
                resource_types = [ResourceType.COPPER_ORE, ResourceType.IRON_ORE,
                                  ResourceType.STEEL_ORE, ResourceType.MITHRIL_ORE]

            # Pick tier and resource
            tier = random.randint(*tier_range)
            tier = min(tier, 4)  # Cap at T4

            # Pick appropriate resource for tier
            valid_resources = [r for r in resource_types if RESOURCE_TIERS[r] <= tier]
            if valid_resources:
                resource_type = random.choice(valid_resources)
                actual_tier = RESOURCE_TIERS[resource_type]  # Use correct tier!
                resource = NaturalResource(pos, resource_type, actual_tier)
                self.resources.append(resource)


# ============================================================================
# WORLD SYSTEM
# ============================================================================
class WorldSystem:
    def __init__(self):
        self.tiles: Dict[str, WorldTile] = {}
        self.chunks: Dict[Tuple[int, int], Chunk] = {}
        self.resources: List[NaturalResource] = []
        self.crafting_stations: List[CraftingStation] = []
        self.generate_world()
        self.spawn_starting_stations()

    def generate_world(self):
        """Generate 100x100 world with chunk-based system"""
        num_chunks = Config.WORLD_SIZE // Config.CHUNK_SIZE

        for chunk_x in range(num_chunks):
            for chunk_y in range(num_chunks):
                chunk = Chunk(chunk_x, chunk_y)
                self.chunks[(chunk_x, chunk_y)] = chunk
                self.tiles.update(chunk.tiles)
                self.resources.extend(chunk.resources)

        print(f"Generated world: {Config.WORLD_SIZE}x{Config.WORLD_SIZE} units")
        print(f"Total chunks: {len(self.chunks)}")
        print(f"Total tiles: {len(self.tiles)}")
        print(f"Total resources: {len(self.resources)}")

    def spawn_starting_stations(self):
        """Spawn starting crafting stations near spawn"""
        # Place stations in a circle around spawn point (50, 50)
        station_positions = [
            (45, 45, StationType.SMITHING),
            (55, 45, StationType.ALCHEMY),
            (55, 55, StationType.REFINING),
            (45, 55, StationType.ENGINEERING),
            (50, 42, StationType.ADORNMENTS),
        ]

        for x, y, station_type in station_positions:
            station = CraftingStation(
                position=Position(x, y, 0),
                station_type=station_type,
                tier=1
            )
            self.crafting_stations.append(station)

        print(f"Spawned {len(self.crafting_stations)} crafting stations")

    def get_tile(self, position: Position) -> Optional[WorldTile]:
        """Get tile at position"""
        return self.tiles.get(position.snap_to_grid().to_key())

    def is_walkable(self, position: Position) -> bool:
        """Check if position is walkable"""
        tile = self.get_tile(position)
        if tile is None:
            return False
        if tile.tile_type == TileType.WATER:
            return False
        return tile.walkable

    def get_visible_tiles(self, camera_pos: Position, viewport_width: int, viewport_height: int) -> List[WorldTile]:
        """Get tiles visible in viewport"""
        tiles_wide = viewport_width // Config.TILE_SIZE + 2
        tiles_high = viewport_height // Config.TILE_SIZE + 2

        start_x = int(camera_pos.x - tiles_wide // 2)
        start_y = int(camera_pos.y - tiles_high // 2)

        visible = []
        for x in range(start_x, start_x + tiles_wide):
            for y in range(start_y, start_y + tiles_high):
                pos = Position(x, y, 0)
                tile = self.get_tile(pos)
                if tile:
                    visible.append(tile)

        return visible

    def get_visible_resources(self, camera_pos: Position, viewport_width: int, viewport_height: int) -> List[
        NaturalResource]:
        """Get resources visible in viewport"""
        tiles_wide = viewport_width // Config.TILE_SIZE + 2
        tiles_high = viewport_height // Config.TILE_SIZE + 2

        start_x = camera_pos.x - tiles_wide // 2
        start_y = camera_pos.y - tiles_high // 2
        end_x = camera_pos.x + tiles_wide // 2
        end_y = camera_pos.y + tiles_high // 2

        visible = []
        for resource in self.resources:
            if (start_x <= resource.position.x <= end_x and
                    start_y <= resource.position.y <= end_y):
                visible.append(resource)

        return visible

    def get_resource_at(self, position: Position) -> Optional[NaturalResource]:
        """Get resource at exact position"""
        snap_pos = position.snap_to_grid()
        for resource in self.resources:
            if (resource.position.x == snap_pos.x and
                    resource.position.y == snap_pos.y and
                    not resource.depleted):
                return resource
        return None

    def get_visible_stations(self, camera_pos: Position, viewport_width: int, viewport_height: int) -> List[
        CraftingStation]:
        """Get crafting stations visible in viewport"""
        tiles_wide = viewport_width // Config.TILE_SIZE + 2
        tiles_high = viewport_height // Config.TILE_SIZE + 2

        start_x = camera_pos.x - tiles_wide // 2
        start_y = camera_pos.y - tiles_high // 2
        end_x = camera_pos.x + tiles_wide // 2
        end_y = camera_pos.y + tiles_high // 2

        visible = []
        for station in self.crafting_stations:
            if (start_x <= station.position.x <= end_x and
                    start_y <= station.position.y <= end_y):
                visible.append(station)

        return visible

    def get_station_at(self, position: Position) -> Optional[CraftingStation]:
        """Get crafting station at exact position"""
        snap_pos = position.snap_to_grid()
        for station in self.crafting_stations:
            if (station.position.x == snap_pos.x and
                    station.position.y == snap_pos.y):
                return station
        return None

    def update(self, dt: float):
        """Update world (resource respawns)"""
        for resource in self.resources:
            resource.update(dt)


# ============================================================================
# CHARACTER STATS
# ============================================================================
@dataclass
class CharacterStats:
    strength: int = 0  # STR
    defense: int = 0  # DEF
    vitality: int = 0  # VIT
    luck: int = 0  # LCK
    agility: int = 0  # AGI
    intelligence: int = 0  # INT

    def get_bonus(self, stat_name: str) -> float:
        """Get percentage bonus from stat (5% per point for most)"""
        stat_value = getattr(self, stat_name.lower(), 0)

        # Different scaling per stat type (from JSON definitions)
        scaling = {
            'strength': 0.05,  # +5% per point
            'defense': 0.02,  # +2% per point
            'vitality': 0.01,  # +1% per point
            'luck': 0.02,  # +2% per point
            'agility': 0.05,  # +5% per point (forestry)
            'intelligence': 0.02  # +2% per point
        }

        return stat_value * scaling.get(stat_name.lower(), 0.05)

    def get_flat_bonus(self, stat_name: str, bonus_type: str) -> float:
        """Get flat bonus from stat (varies by type)"""
        stat_value = getattr(self, stat_name.lower(), 0)

        # Flat bonuses (from JSON definitions)
        if stat_name == 'strength' and bonus_type == 'carry_capacity':
            return stat_value * 10
        elif stat_name == 'vitality' and bonus_type == 'max_health':
            return stat_value * 15
        elif stat_name == 'intelligence' and bonus_type == 'mana':
            return stat_value * 20

        return 0


# ============================================================================
# TITLE SYSTEM
# ============================================================================
@dataclass
class Title:
    """Title earned by player"""
    title_id: str
    name: str
    tier: str  # novice, apprentice, journeyman, expert, master
    category: str  # gathering, crafting, combat
    bonus_description: str
    bonus_value: float
    earned_at_activity_count: int = 0


class TitleSystem:
    """Manages player titles and progression"""

    def __init__(self):
        self.earned_titles: List[Title] = []

        # Hardcoded Novice title thresholds (from JSON design)
        self.novice_thresholds = {
            'novice_miner': ('mining', 100, '+10% mining damage'),
            'novice_lumberjack': ('forestry', 100, '+10% forestry damage'),
            'novice_smith': ('smithing', 50, '+10% smithing time'),
            'novice_refiner': ('refining', 50, '+10% refining precision'),
            'novice_alchemist': ('alchemy', 50, '+10% alchemy progress'),
            'novice_engineer': ('engineering', 20, '+10% engineering tolerance'),
            'novice_enchanter': ('enchanting', 20, '+10% enchanting precision'),
            'novice_warrior': ('combat', 50, '+10% melee damage'),
            'novice_explorer': ('exploration', 1, '+10% discovery chance')  # First rare material
        }

    def check_for_title(self, activity_type: str, count: int) -> Optional[Title]:
        """Check if player earned a title"""
        # Check novice titles
        for title_id, (activity, threshold, bonus_desc) in self.novice_thresholds.items():
            if activity == activity_type and count == threshold:
                # Check if already earned
                if any(t.title_id == title_id for t in self.earned_titles):
                    continue

                # Award title
                title = Title(
                    title_id=title_id,
                    name=title_id.replace('_', ' ').title(),
                    tier='novice',
                    category=activity_type,
                    bonus_description=bonus_desc,
                    bonus_value=0.10,
                    earned_at_activity_count=count
                )
                self.earned_titles.append(title)
                return title

        return None

    def get_total_bonus(self, category: str) -> float:
        """Get total bonus from all titles in category"""
        total = 0.0
        for title in self.earned_titles:
            if title.category == category:
                total += title.bonus_value
        return total


# ============================================================================
# LEVELING SYSTEM
# ============================================================================
class LevelingSystem:
    """Manages character leveling and EXP"""

    def __init__(self):
        self.level = 1
        self.current_exp = 0
        self.max_level = 30

        # EXP curve from JSON (exponential)
        self.exp_requirements = self._generate_exp_curve()

        # Unallocated stat points
        self.unallocated_stat_points = 0

    def _generate_exp_curve(self) -> Dict[int, int]:
        """Generate exponential EXP curve (total ~250,000 for level 30)"""
        curve = {}
        base = 200
        for level in range(1, self.max_level + 1):
            # Exponential scaling: 200, 350, 550, 800, 1100...
            curve[level] = int(base * (1.75 ** (level - 1)))
        return curve

    def get_exp_for_next_level(self) -> int:
        """Get EXP needed for next level"""
        if self.level >= self.max_level:
            return 0
        return self.exp_requirements.get(self.level + 1, 0)

    def add_exp(self, amount: int, source: str = "") -> bool:
        """Add EXP, return True if leveled up"""
        if self.level >= self.max_level:
            return False

        self.current_exp += amount
        exp_needed = self.get_exp_for_next_level()

        if self.current_exp >= exp_needed:
            self.current_exp -= exp_needed
            self.level += 1
            self.unallocated_stat_points += 1
            print(f"🎉 LEVEL UP! Now level {self.level} (+1 stat point)")
            return True

        return False


# ============================================================================
# CLASS SYSTEM
# ============================================================================
@dataclass
class ClassDefinition:
    """Class definition"""
    class_id: str
    name: str
    description: str
    bonuses: Dict[str, float]
    starting_skill: str
    recommended_stats: List[str]


class ClassSystem:
    """Manages player class"""

    def __init__(self):
        self.current_class: Optional[ClassDefinition] = None
        self.classes = self._define_classes()

    def _define_classes(self) -> Dict[str, ClassDefinition]:
        """Define the 6 base classes (from JSON design)"""
        return {
            'warrior': ClassDefinition(
                class_id='warrior',
                name='Warrior',
                description='Master of melee combat',
                bonuses={'max_hp': 30, 'melee_damage': 0.10, 'inventory_slots': 20},
                starting_skill='battle_rage',
                recommended_stats=['strength', 'vitality', 'defense']
            ),
            'ranger': ClassDefinition(
                class_id='ranger',
                name='Ranger',
                description='Swift and precise',
                bonuses={'movement_speed': 0.15, 'crit_chance': 0.10, 'forestry': 0.10},
                starting_skill='forestry_frenzy',
                recommended_stats=['agility', 'luck', 'vitality']
            ),
            'scholar': ClassDefinition(
                class_id='scholar',
                name='Scholar',
                description='Master of knowledge',
                bonuses={'max_mana': 100, 'recipe_discovery': 0.10, 'skill_exp': 0.05},
                starting_skill='alchemists_touch',
                recommended_stats=['intelligence', 'luck', 'agility']
            ),
            'artisan': ClassDefinition(
                class_id='artisan',
                name='Artisan',
                description='Master craftsman',
                bonuses={'craft_time': 0.10, 'first_try_bonus': 0.10, 'durability': 0.05},
                starting_skill='smithing_focus',
                recommended_stats=['agility', 'intelligence', 'luck']
            ),
            'scavenger': ClassDefinition(
                class_id='scavenger',
                name='Scavenger',
                description='Fortune finder',
                bonuses={'rare_drops': 0.20, 'resource_quality': 0.10, 'carry_capacity': 100},
                starting_skill='treasure_hunters_luck',
                recommended_stats=['luck', 'strength', 'vitality']
            ),
            'guardian': ClassDefinition(
                class_id='guardian',
                name='Guardian',
                description='Unbreakable defender',
                bonuses={'max_hp': 50, 'damage_reduction': 0.15, 'armor_effectiveness': 0.20},
                starting_skill='iron_skin',
                recommended_stats=['defense', 'vitality', 'strength']
            )
        }

    def select_class(self, class_id: str) -> bool:
        """Select a class"""
        if class_id in self.classes:
            self.current_class = self.classes[class_id]
            return True
        return False

    def get_bonus(self, bonus_type: str) -> float:
        """Get bonus from current class"""
        if self.current_class:
            return self.current_class.bonuses.get(bonus_type, 0.0)
        return 0.0


# ============================================================================
# ACTIVITY TRACKER
# ============================================================================
class ActivityTracker:
    """Tracks all player activities for titles and progression"""

    def __init__(self):
        self.activity_counts = {
            'mining': 0,
            'forestry': 0,
            'smithing': 0,
            'refining': 0,
            'alchemy': 0,
            'engineering': 0,
            'enchanting': 0,
            'combat': 0,
            'exploration': 0
        }

    def record_activity(self, activity_type: str, amount: int = 1):
        """Record an activity"""
        if activity_type in self.activity_counts:
            self.activity_counts[activity_type] += amount

    def get_count(self, activity_type: str) -> int:
        """Get activity count"""
        return self.activity_counts.get(activity_type, 0)


# ============================================================================
# CHARACTER STATS (Enhanced)
# ============================================================================

# ============================================================================
# ITEM & INVENTORY SYSTEM
# ============================================================================
@dataclass
class ItemStack:
    """Represents a stack of items"""
    item_id: str
    quantity: int
    max_stack: int = 99

    def __post_init__(self):
        # Get max stack from material database if available
        mat_db = MaterialDatabase.get_instance()
        if mat_db.loaded:
            mat = mat_db.get_material(self.item_id)
            if mat:
                self.max_stack = mat.max_stack

    def can_add(self, amount: int) -> bool:
        return self.quantity + amount <= self.max_stack

    def add(self, amount: int) -> int:
        """Add items, return overflow"""
        space = self.max_stack - self.quantity
        added = min(space, amount)
        self.quantity += added
        return amount - added

    def get_material(self) -> Optional[MaterialDefinition]:
        """Get material definition for this item"""
        mat_db = MaterialDatabase.get_instance()
        return mat_db.get_material(self.item_id)


class Inventory:
    """Player inventory system"""

    def __init__(self, max_slots: int = 30):
        self.slots: List[Optional[ItemStack]] = [None] * max_slots
        self.max_slots = max_slots

        # Drag and drop state
        self.dragging_slot: Optional[int] = None
        self.dragging_stack: Optional[ItemStack] = None

    def add_item(self, item_id: str, quantity: int) -> bool:
        """Add items to inventory, return True if successful"""
        remaining = quantity

        # Get max stack size from material database
        mat_db = MaterialDatabase.get_instance()
        mat = mat_db.get_material(item_id)
        max_stack = mat.max_stack if mat else 99

        # Try to stack with existing items
        for slot in self.slots:
            if slot and slot.item_id == item_id and remaining > 0:
                overflow = slot.add(remaining)
                remaining = overflow

        # Create new stacks if needed
        while remaining > 0:
            empty_slot = self.get_empty_slot()
            if empty_slot is None:
                return False  # Inventory full

            stack_size = min(remaining, max_stack)
            self.slots[empty_slot] = ItemStack(item_id, stack_size, max_stack)
            remaining -= stack_size

        return True

    def get_empty_slot(self) -> Optional[int]:
        """Get first empty slot index"""
        for i, slot in enumerate(self.slots):
            if slot is None:
                return i
        return None

    def get_item_count(self, item_id: str) -> int:
        """Count total quantity of an item"""
        total = 0
        for slot in self.slots:
            if slot and slot.item_id == item_id:
                total += slot.quantity
        return total

    def start_drag(self, slot_index: int):
        """Start dragging an item"""
        if 0 <= slot_index < self.max_slots and self.slots[slot_index]:
            self.dragging_slot = slot_index
            self.dragging_stack = self.slots[slot_index]
            self.slots[slot_index] = None

    def end_drag(self, target_slot: int):
        """End drag, place item in target slot"""
        if self.dragging_stack is None:
            return

        if 0 <= target_slot < self.max_slots:
            # If target slot is empty
            if self.slots[target_slot] is None:
                self.slots[target_slot] = self.dragging_stack
            # If target has same item, try to stack
            elif self.slots[target_slot].item_id == self.dragging_stack.item_id:
                overflow = self.slots[target_slot].add(self.dragging_stack.quantity)
                if overflow > 0:
                    # Put overflow back in original slot
                    self.dragging_stack.quantity = overflow
                    self.slots[self.dragging_slot] = self.dragging_stack
            # If target has different item, swap
            else:
                self.slots[target_slot], self.dragging_stack = self.dragging_stack, self.slots[target_slot]
                if self.dragging_stack and self.dragging_slot is not None:
                    self.slots[self.dragging_slot] = self.dragging_stack
        else:
            # Invalid target, return to original slot
            self.slots[self.dragging_slot] = self.dragging_stack

        self.dragging_slot = None
        self.dragging_stack = None

    def cancel_drag(self):
        """Cancel drag, return item to original slot"""
        if self.dragging_stack and self.dragging_slot is not None:
            self.slots[self.dragging_slot] = self.dragging_stack

        self.dragging_slot = None
        self.dragging_stack = None


# ============================================================================
# TOOL SYSTEM
# ============================================================================
class ToolType(Enum):
    AXE = "axe"
    PICKAXE = "pickaxe"
    SHOVEL = "shovel"


@dataclass
class Tool:
    """Tool for gathering resources"""
    tool_id: str
    name: str
    tool_type: ToolType
    tier: int
    damage: int  # Harvest damage per hit
    durability_current: int
    durability_max: int
    efficiency: float = 1.0

    def can_harvest(self, resource_tier: int) -> bool:
        """Check if tool tier is sufficient"""
        return self.tier >= resource_tier

    def use(self) -> bool:
        """Use tool (reduce durability), return True if still usable"""
        if self.durability_current <= 0:
            return False

        self.durability_current -= 1
        return True

    def get_effectiveness(self) -> float:
        """Get current effectiveness (0.5 to 1.0 based on durability)"""
        if self.durability_current <= 0:
            return 0.5  # 50% at 0 durability

        durability_percent = self.durability_current / self.durability_max

        if durability_percent >= 0.5:
            return 1.0  # Full effectiveness above 50%
        else:
            # Degrade from 100% to 75% as durability goes 50% -> 0%
            return 1.0 - (0.5 - durability_percent) * 0.5


# ============================================================================
# RESOURCE NODE SYSTEM
# ============================================================================
class ResourceType(Enum):
    # Trees (T1-T4)
    OAK_TREE = "oak_tree"
    BIRCH_TREE = "birch_tree"
    MAPLE_TREE = "maple_tree"
    IRONWOOD_TREE = "ironwood_tree"

    # Ore Veins (T1-T4)
    COPPER_ORE = "copper_ore"
    IRON_ORE = "iron_ore"
    STEEL_ORE = "steel_ore"
    MITHRIL_ORE = "mithril_ore"

    # Stone (T1-T4)
    LIMESTONE = "limestone"
    GRANITE = "granite"
    OBSIDIAN = "obsidian"
    STAR_CRYSTAL = "star_crystal"


# Resource tier mapping (must be defined before NaturalResource class)
RESOURCE_TIERS = {
    ResourceType.OAK_TREE: 1, ResourceType.BIRCH_TREE: 2,
    ResourceType.MAPLE_TREE: 3, ResourceType.IRONWOOD_TREE: 4,
    ResourceType.COPPER_ORE: 1, ResourceType.IRON_ORE: 2,
    ResourceType.STEEL_ORE: 3, ResourceType.MITHRIL_ORE: 4,
    ResourceType.LIMESTONE: 1, ResourceType.GRANITE: 2,
    ResourceType.OBSIDIAN: 3, ResourceType.STAR_CRYSTAL: 4
}


@dataclass
class LootDrop:
    """Item that can drop from resource"""
    item_id: str
    min_quantity: int
    max_quantity: int
    chance: float = 1.0  # 0.0 to 1.0


class NaturalResource:
    """Resource node in the world"""

    def __init__(self, position: Position, resource_type: ResourceType, tier: int):
        self.position = position
        self.resource_type = resource_type
        self.tier = tier

        # HP based on tier
        hp_values = {1: 100, 2: 200, 3: 400, 4: 800}
        self.max_hp = hp_values.get(tier, 100)
        self.current_hp = self.max_hp

        # Tool requirement
        if "tree" in resource_type.value:
            self.required_tool = ToolType.AXE
        elif "ore" in resource_type.value:
            self.required_tool = ToolType.PICKAXE
        else:
            self.required_tool = ToolType.PICKAXE

        # Respawn settings
        if "tree" in resource_type.value:
            self.respawns = True
            self.respawn_timer = 60.0  # 60 seconds
            self.time_until_respawn = 0.0
        else:
            self.respawns = False
            self.respawn_timer = None
            self.time_until_respawn = 0.0

        # Loot table
        self.loot_table = self._generate_loot_table()

        self.depleted = False

    def _generate_loot_table(self) -> List[LootDrop]:
        """Generate loot drops based on resource type"""
        loot = []

        # Trees
        if self.resource_type == ResourceType.OAK_TREE:
            loot.append(LootDrop("oak_log", 2, 4))
        elif self.resource_type == ResourceType.BIRCH_TREE:
            loot.append(LootDrop("birch_log", 2, 4))
        elif self.resource_type == ResourceType.MAPLE_TREE:
            loot.append(LootDrop("maple_log", 2, 5))
        elif self.resource_type == ResourceType.IRONWOOD_TREE:
            loot.append(LootDrop("ironwood_log", 3, 6))

        # Ores
        elif self.resource_type == ResourceType.COPPER_ORE:
            loot.append(LootDrop("copper_ore", 1, 3))
        elif self.resource_type == ResourceType.IRON_ORE:
            loot.append(LootDrop("iron_ore", 1, 3))
        elif self.resource_type == ResourceType.STEEL_ORE:
            loot.append(LootDrop("steel_ore", 2, 4))
        elif self.resource_type == ResourceType.MITHRIL_ORE:
            loot.append(LootDrop("mithril_ore", 2, 5))

        # Stones
        elif self.resource_type == ResourceType.LIMESTONE:
            loot.append(LootDrop("limestone", 1, 2))
        elif self.resource_type == ResourceType.GRANITE:
            loot.append(LootDrop("granite", 1, 2))
        elif self.resource_type == ResourceType.OBSIDIAN:
            loot.append(LootDrop("obsidian", 2, 3))
        elif self.resource_type == ResourceType.STAR_CRYSTAL:
            loot.append(LootDrop("star_crystal", 1, 2))

        return loot

    def take_damage(self, damage: int, is_crit: bool = False) -> Tuple[int, bool]:
        """
        Take damage from harvesting
        Returns: (actual_damage, was_depleted)
        """
        if self.depleted:
            return 0, False

        actual_damage = damage * 2 if is_crit else damage
        self.current_hp -= actual_damage

        if self.current_hp <= 0:
            self.current_hp = 0
            self.depleted = True
            return actual_damage, True

        return actual_damage, False

    def get_loot(self) -> List[Tuple[str, int]]:
        """Generate loot drops when depleted"""
        drops = []
        for loot in self.loot_table:
            if random.random() <= loot.chance:
                quantity = random.randint(loot.min_quantity, loot.max_quantity)
                drops.append((loot.item_id, quantity))
        return drops

    def update(self, dt: float):
        """Update resource (respawn timer)"""
        if self.depleted and self.respawns:
            self.time_until_respawn += dt
            if self.time_until_respawn >= self.respawn_timer:
                self.respawn()

    def respawn(self):
        """Respawn the resource"""
        self.current_hp = self.max_hp
        self.depleted = False
        self.time_until_respawn = 0.0

    def get_color(self) -> Tuple[int, int, int]:
        """Get display color based on type"""
        if self.depleted:
            return (50, 50, 50)  # Gray when depleted

        if "tree" in self.resource_type.value:
            return Config.COLOR_TREE
        elif "ore" in self.resource_type.value:
            return Config.COLOR_ORE
        else:
            return Config.COLOR_STONE_NODE


# ============================================================================
# CRAFTING SYSTEM
# ============================================================================
class StationType(Enum):
    SMITHING = "smithing"
    ALCHEMY = "alchemy"
    REFINING = "refining"
    ENGINEERING = "engineering"
    ADORNMENTS = "adornments"


@dataclass
class Recipe:
    """Recipe definition loaded from JSON"""
    recipe_id: str
    output_id: str
    output_qty: int
    station_type: str
    station_tier: int
    inputs: List[Dict]
    grid_size: str = "3x3"
    mini_game_type: str = ""
    metadata: Dict = field(default_factory=dict)


class RecipeDatabase:
    """Global recipe database loaded from JSON"""
    _instance = None

    def __init__(self):
        self.recipes: Dict[str, Recipe] = {}
        self.recipes_by_station: Dict[str, List[Recipe]] = {
            "smithing": [],
            "alchemy": [],
            "refining": [],
            "engineering": [],
            "adornments": []
        }
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = RecipeDatabase()
        return cls._instance

    def load_from_files(self, base_path: str = ""):
        """Load all recipe files"""
        recipe_files = [
            ("smithing", "recipes-smithing-3.json"),
            ("alchemy", "recipes-alchemy-1.json"),
            ("refining", "recipes-refining-1.json"),
            ("engineering", "recipes-engineering-1.json"),
            ("adornments", "recipes-adornments-1.json")
        ]

        total_loaded = 0

        for station_type, filename in recipe_files:
            # Try multiple paths
            possible_paths = [
                f"{base_path}data/{filename}",
                f"{base_path}../data/{filename}",
                f"{base_path}../../data/{filename}",
                f"Game-1/recipes.JSON/{filename}",
                f"../Game-1/recipes.JSON/{filename}",
            ]

            loaded = False
            for path in possible_paths:
                if Path(path).exists():
                    count = self._load_recipe_file(path, station_type)
                    if count > 0:
                        print(f"  ✓ Loaded {count} {station_type} recipes from {filename}")
                        total_loaded += count
                        loaded = True
                        break

            if not loaded:
                print(f"  ⚠ Could not find {filename}, skipping...")

        self.loaded = True
        print(f"✓ Total recipes loaded: {total_loaded}")

        if total_loaded == 0:
            print("⚠ No recipes loaded - creating placeholders...")
            self._create_placeholder_recipes()

    def _load_recipe_file(self, filepath: str, station_type: str) -> int:
        """Load recipes from a single JSON file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            recipes_list = data.get('recipes', [])

            for recipe_data in recipes_list:
                recipe = Recipe(
                    recipe_id=recipe_data.get('recipeId', ''),
                    output_id=recipe_data.get('outputId', ''),
                    output_qty=recipe_data.get('outputQty', 1),
                    station_type=recipe_data.get('stationType', station_type),
                    station_tier=recipe_data.get('stationTier', 1),
                    inputs=recipe_data.get('inputs', []),
                    grid_size=recipe_data.get('gridSize', '3x3'),
                    mini_game_type=recipe_data.get('miniGame', {}).get('type', station_type),
                    metadata=recipe_data.get('metadata', {})
                )

                self.recipes[recipe.recipe_id] = recipe
                self.recipes_by_station[station_type].append(recipe)

            return len(recipes_list)

        except Exception as e:
            print(f"  ✗ Error loading {filepath}: {e}")
            return 0

    def _create_placeholder_recipes(self):
        """Create placeholder recipes for testing"""
        placeholders = [
            Recipe("placeholder_sword", "iron_sword", 1, "smithing", 1,
                   [{"materialId": "iron_ingot", "quantity": 3}, {"materialId": "oak_log", "quantity": 1}],
                   "3x3", "smithing", {"narrative": "A basic iron sword"}),
            Recipe("placeholder_potion", "health_potion", 1, "alchemy", 1,
                   [{"materialId": "oak_log", "quantity": 2}],
                   "3x3", "alchemy", {"narrative": "A simple healing potion"}),
        ]

        for recipe in placeholders:
            self.recipes[recipe.recipe_id] = recipe
            self.recipes_by_station[recipe.station_type].append(recipe)

        print(f"✓ Created {len(placeholders)} placeholder recipes")

    def get_recipes_for_station(self, station_type: str, tier: int = 1) -> List[Recipe]:
        """Get all recipes for a station type at or below the given tier"""
        return [r for r in self.recipes_by_station.get(station_type, [])
                if r.station_tier <= tier]

    def can_craft(self, recipe: Recipe, inventory: Inventory) -> bool:
        """Check if player has materials to craft recipe"""
        for input_mat in recipe.inputs:
            mat_id = input_mat.get('materialId', '')
            required_qty = input_mat.get('quantity', 0)
            available = inventory.get_item_count(mat_id)

            if available < required_qty:
                return False

        return True

    def consume_materials(self, recipe: Recipe, inventory: Inventory) -> bool:
        """Remove materials from inventory for crafting"""
        # First check if we can craft
        if not self.can_craft(recipe, inventory):
            return False

        # Remove materials
        for input_mat in recipe.inputs:
            mat_id = input_mat.get('materialId', '')
            required_qty = input_mat.get('quantity', 0)

            # Remove from inventory slots
            remaining = required_qty
            for slot in inventory.slots:
                if slot and slot.item_id == mat_id and remaining > 0:
                    if slot.quantity >= remaining:
                        slot.quantity -= remaining
                        if slot.quantity == 0:
                            # Remove empty slot
                            idx = inventory.slots.index(slot)
                            inventory.slots[idx] = None
                        remaining = 0
                        break
                    else:
                        remaining -= slot.quantity
                        idx = inventory.slots.index(slot)
                        inventory.slots[idx] = None

        return True


@dataclass
class CraftingStation:
    """Crafting station in the world"""
    position: Position
    station_type: StationType
    tier: int

    def get_color(self) -> Tuple[int, int, int]:
        """Get station color based on type"""
        colors = {
            StationType.SMITHING: (180, 60, 60),  # Red
            StationType.ALCHEMY: (60, 180, 60),  # Green
            StationType.REFINING: (180, 120, 60),  # Orange
            StationType.ENGINEERING: (60, 120, 180),  # Blue
            StationType.ADORNMENTS: (180, 60, 180)  # Purple
        }
        return colors.get(self.station_type, (150, 150, 150))


# ============================================================================
# DAMAGE NUMBER FEEDBACK
# ============================================================================
@dataclass
class DamageNumber:
    """Floating damage number for visual feedback"""
    damage: int
    position: Position
    is_crit: bool
    lifetime: float = 1.0
    velocity_y: float = -1.0

    def update(self, dt: float) -> bool:
        """Update position and lifetime, return False when expired"""
        self.lifetime -= dt
        self.position.y += self.velocity_y * dt
        return self.lifetime > 0


# ============================================================================
# CHARACTER SYSTEM
# ============================================================================
class Character:
    def __init__(self, start_position: Position):
        self.position = start_position
        self.facing = "down"
        self.movement_speed = Config.PLAYER_SPEED
        self.interaction_range = Config.INTERACTION_RANGE

        # Stats (all start at 0, allocate from level-ups)
        self.stats = CharacterStats()

        # Progression systems
        self.leveling = LevelingSystem()
        self.skills = SkillManager()
        self.titles = TitleSystem()
        self.class_system = ClassSystem()
        self.activities = ActivityTracker()

        # Health & Mana
        self.max_health = 100 + self.stats.get_flat_bonus('vitality', 'max_health')
        self.health = self.max_health
        self.max_mana = 100 + self.stats.get_flat_bonus('intelligence', 'mana')
        self.mana = self.max_mana

        # Movement
        self.velocity = Position(0, 0, 0)

        # Inventory & Tools
        self.inventory = Inventory(30)
        self.tools: List[Tool] = []
        self.selected_tool: Optional[Tool] = None

        # Crafting
        self.active_station: Optional[CraftingStation] = None
        self.crafting_ui_open = False

        # UI State
        self.stats_ui_open = False

        # Give starting tools
        self._give_starting_tools()

    def _give_starting_tools(self):
        """Give player starting T1 tools"""
        t1_axe = Tool(
            tool_id="copper_axe",
            name="Copper Axe",
            tool_type=ToolType.AXE,
            tier=1,
            damage=10,
            durability_current=500,
            durability_max=500
        )
        t1_pickaxe = Tool(
            tool_id="copper_pickaxe",
            name="Copper Pickaxe",
            tool_type=ToolType.PICKAXE,
            tier=1,
            damage=10,
            durability_current=500,
            durability_max=500
        )

        self.tools = [t1_axe, t1_pickaxe]
        self.selected_tool = t1_axe

    def allocate_stat_point(self, stat_name: str) -> bool:
        """Allocate a stat point"""
        if self.leveling.unallocated_stat_points <= 0:
            return False

        if hasattr(self.stats, stat_name):
            current_value = getattr(self.stats, stat_name)
            setattr(self.stats, stat_name, current_value + 1)
            self.leveling.unallocated_stat_points -= 1

            # Recalculate derived stats
            self.max_health = 100 + self.stats.get_flat_bonus('vitality', 'max_health')
            self.max_mana = 100 + self.stats.get_flat_bonus('intelligence', 'mana')

            return True

        return False

    def move(self, dx: float, dy: float, world: WorldSystem) -> bool:
        """Move character with collision detection"""
        # Apply agility bonus to movement speed
        agility_bonus = self.stats.get_bonus('agility') * 0.02  # +2% per AGI
        class_bonus = self.class_system.get_bonus('movement_speed')
        speed_mult = 1.0 + agility_bonus + class_bonus

        new_pos = Position(
            self.position.x + dx * speed_mult,
            self.position.y + dy * speed_mult,
            self.position.z
        )

        # Check bounds
        if new_pos.x < 0 or new_pos.x >= Config.WORLD_SIZE:
            return False
        if new_pos.y < 0 or new_pos.y >= Config.WORLD_SIZE:
            return False

        # Check if walkable
        if world.is_walkable(new_pos):
            self.position = new_pos

            # Update facing direction
            if abs(dx) > abs(dy):
                self.facing = "right" if dx > 0 else "left"
            else:
                self.facing = "down" if dy > 0 else "up"

            return True

        return False

    def is_in_range(self, target_position: Position) -> bool:
        """Check if target is within interaction range"""
        return self.position.distance_to(target_position) <= self.interaction_range

    def harvest_resource(self, resource: NaturalResource) -> Optional[
        Tuple[Optional[List[Tuple[str, int]]], int, bool]]:
        """
        Attempt to harvest a resource node
        Returns: (loot, actual_damage, is_crit) or None if failed
        """
        if not self.selected_tool:
            return None

        # Check if in range
        if not self.is_in_range(resource.position):
            return None

        # Check if correct tool type
        if self.selected_tool.tool_type != resource.required_tool:
            return None

        # Check if tool tier is sufficient
        if not self.selected_tool.can_harvest(resource.tier):
            return None

        # Calculate damage with stat bonuses
        base_damage = self.selected_tool.damage
        effectiveness = self.selected_tool.get_effectiveness()

        # Apply STR bonus for mining, AGI bonus for forestry
        if resource.required_tool == ToolType.PICKAXE:
            stat_bonus = self.stats.get_bonus('strength')
            activity_type = 'mining'
        elif resource.required_tool == ToolType.AXE:
            stat_bonus = self.stats.get_bonus('agility')
            activity_type = 'forestry'
        else:
            stat_bonus = 0.0
            activity_type = 'gathering'

        # Apply title bonuses
        title_bonus = self.titles.get_total_bonus(activity_type)

        # Total damage multiplier
        damage_mult = 1.0 + stat_bonus + title_bonus

        # Check for critical hit (LCK-based)
        base_crit_chance = self.stats.luck * 0.02  # 2% per LCK
        class_crit_bonus = self.class_system.get_bonus('crit_chance')
        crit_chance = base_crit_chance + class_crit_bonus
        is_crit = random.random() < crit_chance

        damage = int(base_damage * effectiveness * damage_mult)

        # Apply damage to resource
        actual_damage, depleted = resource.take_damage(damage, is_crit)

        # Use tool durability (with VIT/DEF reduction)
        durability_reduction = 1.0 - self.stats.get_bonus('vitality') - self.stats.get_bonus('defense') * 0.02
        durability_reduction = max(0.5, durability_reduction)  # Min 50% consumption

        if not self.selected_tool.use():
            print("⚠ Tool broke!")

        # Record activity
        self.activities.record_activity(activity_type, 1)

        # Check for title
        count = self.activities.get_count(activity_type)
        new_title = self.titles.check_for_title(activity_type, count)
        if new_title:
            print(f"🏆 TITLE EARNED: {new_title.name} - {new_title.bonus_description}")

        # Award EXP (tier-based, 4x multiplier)
        exp_values = {1: 10, 2: 40, 3: 160, 4: 640}
        exp_gain = exp_values.get(resource.tier, 10)
        self.leveling.add_exp(exp_gain, f"Harvested T{resource.tier} resource")

        # If depleted, get loot
        loot = None
        if depleted:
            loot = resource.get_loot()

            # Apply LCK bonus to yield
            luck_bonus = self.stats.luck * 0.02  # +2% per LCK
            quality_bonus = self.class_system.get_bonus('resource_quality')

            # Add to inventory
            for item_id, quantity in loot:
                # Bonus quantity chance
                bonus_chance = luck_bonus + quality_bonus
                if random.random() < bonus_chance:
                    quantity += 1

                self.inventory.add_item(item_id, quantity)

        # Return damage info for feedback
        return (loot, actual_damage, is_crit)

    def switch_tool(self):
        """Cycle through available tools"""
        if not self.tools:
            return

        current_idx = self.tools.index(self.selected_tool) if self.selected_tool in self.tools else -1
        next_idx = (current_idx + 1) % len(self.tools)
        self.selected_tool = self.tools[next_idx]

    def interact_with_station(self, station: CraftingStation):
        """Open crafting UI for station"""
        if self.is_in_range(station.position):
            self.active_station = station
            self.crafting_ui_open = True

    def close_crafting_ui(self):
        """Close crafting UI"""
        self.active_station = None
        self.crafting_ui_open = False

    def toggle_stats_ui(self):
        """Toggle stats/progression UI"""
        self.stats_ui_open = not self.stats_ui_open


# ============================================================================
# CAMERA/VIEWPORT SYSTEM
# ============================================================================
class Camera:
    def __init__(self, viewport_width: int, viewport_height: int):
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.position = Position(0, 0, 0)

    def follow(self, target: Position):
        """Camera follows target (player)"""
        self.position = target.copy()

    def world_to_screen(self, world_pos: Position) -> Tuple[int, int]:
        """Convert world position to screen coordinates"""
        screen_x = (world_pos.x - self.position.x) * Config.TILE_SIZE + self.viewport_width // 2
        screen_y = (world_pos.y - self.position.y) * Config.TILE_SIZE + self.viewport_height // 2
        return int(screen_x), int(screen_y)


# ============================================================================
# RENDERER
# ============================================================================
class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)

    def render_world(self, world: WorldSystem, camera: Camera, character: Character,
                     damage_numbers: List[DamageNumber]):
        """Render the game world"""
        # Clear viewport area
        pygame.draw.rect(self.screen, Config.COLOR_BACKGROUND,
                         (0, 0, Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT))

        # Get visible tiles
        visible_tiles = world.get_visible_tiles(
            camera.position,
            Config.VIEWPORT_WIDTH,
            Config.VIEWPORT_HEIGHT
        )

        # Render tiles
        for tile in visible_tiles:
            screen_x, screen_y = camera.world_to_screen(tile.position)

            # Only draw if on screen
            if -Config.TILE_SIZE <= screen_x <= Config.VIEWPORT_WIDTH and \
                    -Config.TILE_SIZE <= screen_y <= Config.VIEWPORT_HEIGHT:
                rect = pygame.Rect(screen_x, screen_y, Config.TILE_SIZE, Config.TILE_SIZE)
                pygame.draw.rect(self.screen, tile.get_color(), rect)
                pygame.draw.rect(self.screen, Config.COLOR_GRID, rect, 1)

        # Render crafting stations
        visible_stations = world.get_visible_stations(
            camera.position,
            Config.VIEWPORT_WIDTH,
            Config.VIEWPORT_HEIGHT
        )
        self.render_stations(camera, visible_stations, character)

        # Render resources
        visible_resources = world.get_visible_resources(
            camera.position,
            Config.VIEWPORT_WIDTH,
            Config.VIEWPORT_HEIGHT
        )
        self.render_resources(camera, visible_resources, character)

        # Render interaction range
        self.render_interaction_range(camera, character)

        # Render character
        self.render_character(camera, character)

        # Render damage numbers
        self.render_damage_numbers(camera, damage_numbers)

    def render_stations(self, camera: Camera, stations: List[CraftingStation], character: Character):
        """Render crafting stations"""
        for station in stations:
            screen_x, screen_y = camera.world_to_screen(station.position)

            # Check if in interaction range
            in_range = character.is_in_range(station.position)

            # Draw station as diamond shape
            color = station.get_color()
            if not in_range:
                # Dim if out of range
                color = tuple(max(0, c - 50) for c in color)

            size = Config.TILE_SIZE - 8
            points = [
                (screen_x, screen_y - size // 2),  # Top
                (screen_x + size // 2, screen_y),  # Right
                (screen_x, screen_y + size // 2),  # Bottom
                (screen_x - size // 2, screen_y),  # Left
            ]
            pygame.draw.polygon(self.screen, color, points)
            pygame.draw.polygon(self.screen, (0, 0, 0), points, 3)

            # Draw tier badge
            if in_range:
                tier_text = f"T{station.tier}"
                tier_surface = self.small_font.render(tier_text, True, (255, 255, 255))
                tier_rect = tier_surface.get_rect(center=(screen_x, screen_y))

                # Black outline
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    outline_rect = tier_rect.copy()
                    outline_rect.x += dx
                    outline_rect.y += dy
                    outline_surface = self.small_font.render(tier_text, True, (0, 0, 0))
                    self.screen.blit(outline_surface, outline_rect)

                self.screen.blit(tier_surface, tier_rect)

    def render_resources(self, camera: Camera, resources: List[NaturalResource], character: Character):
        """Render resource nodes"""
        for resource in resources:
            if resource.depleted and not resource.respawns:
                continue  # Don't render permanently depleted nodes

            screen_x, screen_y = camera.world_to_screen(resource.position)

            # Check if in interaction range
            in_range = character.is_in_range(resource.position)

            # Draw resource
            color = resource.get_color()
            if not in_range:
                # Dim if out of range
                color = tuple(max(0, c - 50) for c in color)

            # Draw as square
            size = Config.TILE_SIZE - 4
            rect = pygame.Rect(screen_x - size // 2, screen_y - size // 2, size, size)
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, (0, 0, 0), rect, 2)

            # Draw HP bar if not depleted and in range
            if not resource.depleted and in_range:
                self.render_resource_hp_bar(screen_x, screen_y, resource)

            # Draw respawn indicator if depleted and respawns
            if resource.depleted and resource.respawns:
                respawn_pct = resource.time_until_respawn / resource.respawn_timer
                text = f"{int(resource.respawn_timer - resource.time_until_respawn)}s"
                text_surface = self.small_font.render(text, True, (200, 200, 200))
                text_rect = text_surface.get_rect(center=(screen_x, screen_y))
                self.screen.blit(text_surface, text_rect)

    def render_resource_hp_bar(self, x: int, y: int, resource: NaturalResource):
        """Render HP bar above resource"""
        bar_width = Config.TILE_SIZE - 8
        bar_height = 4
        bar_y = y - Config.TILE_SIZE // 2 - 8

        # Background
        bg_rect = pygame.Rect(x - bar_width // 2, bar_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, Config.COLOR_HP_BAR_BG, bg_rect)

        # HP fill
        hp_percent = resource.current_hp / resource.max_hp
        hp_width = int(bar_width * hp_percent)
        hp_rect = pygame.Rect(x - bar_width // 2, bar_y, hp_width, bar_height)
        pygame.draw.rect(self.screen, Config.COLOR_HP_BAR, hp_rect)

    def render_damage_numbers(self, camera: Camera, damage_numbers: List[DamageNumber]):
        """Render floating damage numbers"""
        for dmg_num in damage_numbers:
            screen_x, screen_y = camera.world_to_screen(dmg_num.position)

            # Fade out based on lifetime
            alpha = int(255 * (dmg_num.lifetime / 1.0))
            color = Config.COLOR_DAMAGE_CRIT if dmg_num.is_crit else Config.COLOR_DAMAGE_NORMAL

            text = str(dmg_num.damage)
            if dmg_num.is_crit:
                text = f"{text}!"

            font = self.font if dmg_num.is_crit else self.small_font
            text_surface = font.render(text, True, color)

            # Apply alpha
            text_surface.set_alpha(alpha)

            text_rect = text_surface.get_rect(center=(screen_x, screen_y))
            self.screen.blit(text_surface, text_rect)

    def render_interaction_range(self, camera: Camera, character: Character):
        """Render interaction range circle around player"""
        center_x, center_y = camera.world_to_screen(character.position)
        radius = int(character.interaction_range * Config.TILE_SIZE)

        # Create surface with alpha for transparency
        circle_surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(circle_surface, Config.COLOR_INTERACTION_RANGE,
                           (radius, radius), radius)

        self.screen.blit(circle_surface,
                         (center_x - radius, center_y - radius))

    def render_character(self, camera: Camera, character: Character):
        """Render player character"""
        screen_x, screen_y = camera.world_to_screen(character.position)

        # Draw character as circle for now
        pygame.draw.circle(self.screen, Config.COLOR_PLAYER,
                           (screen_x, screen_y),
                           Config.TILE_SIZE // 3)

        # Draw facing indicator
        if character.facing == "up":
            offset = (0, -Config.TILE_SIZE // 2)
        elif character.facing == "down":
            offset = (0, Config.TILE_SIZE // 2)
        elif character.facing == "left":
            offset = (-Config.TILE_SIZE // 2, 0)
        else:  # right
            offset = (Config.TILE_SIZE // 2, 0)

        pygame.draw.line(self.screen, (255, 255, 255),
                         (screen_x, screen_y),
                         (screen_x + offset[0], screen_y + offset[1]), 2)

    def render_ui(self, character: Character, mouse_pos: Optional[Tuple[int, int]] = None):
        """Render UI panel on right side"""
        # UI background
        ui_rect = pygame.Rect(Config.VIEWPORT_WIDTH, 0,
                              Config.UI_PANEL_WIDTH, Config.VIEWPORT_HEIGHT)
        pygame.draw.rect(self.screen, Config.COLOR_UI_BG, ui_rect)

        y_offset = 20

        # Character Info
        self.render_text("CHARACTER INFO", Config.VIEWPORT_WIDTH + 20, y_offset, bold=True)
        y_offset += 40

        # Position
        pos_text = f"Position: ({character.position.x:.1f}, {character.position.y:.1f})"
        self.render_text(pos_text, Config.VIEWPORT_WIDTH + 20, y_offset, small=True)
        y_offset += 25

        # Level & XP
        level_text = f"Level: {character.leveling.level}"
        if character.leveling.unallocated_stat_points > 0:
            level_text += f" ({character.leveling.unallocated_stat_points} points available!)"
        self.render_text(level_text, Config.VIEWPORT_WIDTH + 20, y_offset, small=True)
        y_offset += 20

        exp_needed = character.leveling.get_exp_for_next_level()
        if exp_needed > 0:
            xp_text = f"XP: {character.leveling.current_exp}/{exp_needed}"
            self.render_text(xp_text, Config.VIEWPORT_WIDTH + 20, y_offset, small=True)
            y_offset += 30
        else:
            self.render_text("MAX LEVEL", Config.VIEWPORT_WIDTH + 20, y_offset, small=True)
            y_offset += 30

        # Health & Mana bars
        self.render_health_bar(character, Config.VIEWPORT_WIDTH + 20, y_offset)
        y_offset += 35
        self.render_mana_bar(character, Config.VIEWPORT_WIDTH + 20, y_offset)
        y_offset += 50

        # Selected Tool
        self.render_text("SELECTED TOOL", Config.VIEWPORT_WIDTH + 20, y_offset, bold=True)
        y_offset += 30

        if character.selected_tool:
            tool = character.selected_tool
            self.render_text(f"{tool.name} (T{tool.tier})", Config.VIEWPORT_WIDTH + 20, y_offset, small=True)
            y_offset += 20
            dur_text = f"Durability: {tool.durability_current}/{tool.durability_max}"
            self.render_text(dur_text, Config.VIEWPORT_WIDTH + 20, y_offset, small=True)
            y_offset += 20
            eff_text = f"Effectiveness: {tool.get_effectiveness() * 100:.0f}%"
            self.render_text(eff_text, Config.VIEWPORT_WIDTH + 20, y_offset, small=True)
            y_offset += 20
            dmg_text = f"Damage: {tool.damage}"
            self.render_text(dmg_text, Config.VIEWPORT_WIDTH + 20, y_offset, small=True)
            y_offset += 30

        # Class Info
        if character.class_system.current_class:
            self.render_text("CLASS", Config.VIEWPORT_WIDTH + 20, y_offset, bold=True)
            y_offset += 30
            self.render_text(character.class_system.current_class.name, Config.VIEWPORT_WIDTH + 20, y_offset,
                             small=True)
            y_offset += 25

        # Titles (show count)
        title_count = len(character.titles.earned_titles)
        self.render_text(f"TITLES EARNED: {title_count}", Config.VIEWPORT_WIDTH + 20, y_offset, bold=True)
        y_offset += 30

        # Show last 2 titles
        for title in character.titles.earned_titles[-2:]:
            self.render_text(f"• {title.name}", Config.VIEWPORT_WIDTH + 20, y_offset, small=True)
            y_offset += 18

        if title_count > 0:
            y_offset += 10

        # Controls
        self.render_text("CONTROLS", Config.VIEWPORT_WIDTH + 20, y_offset, bold=True)
        y_offset += 30

        controls = [
            "WASD - Move",
            "CLICK - Harvest/Interact",
            "TAB - Switch tool",
            "C - Character Stats",
            "DRAG - Move items",
            "ESC - Close UI/Quit",
        ]

        for control_text in controls:
            self.render_text(control_text, Config.VIEWPORT_WIDTH + 20, y_offset, small=True)
            y_offset += 22

    def render_mana_bar(self, character: Character, x: int, y: int):
        """Render mana bar"""
        bar_width = 300
        bar_height = 20

        # Background
        bg_rect = pygame.Rect(x, y, bar_width, bar_height)
        pygame.draw.rect(self.screen, Config.COLOR_HEALTH_BG, bg_rect)

        # Mana fill (blue)
        mana_percent = character.mana / character.max_mana
        mana_width = int(bar_width * mana_percent)
        mana_rect = pygame.Rect(x, y, mana_width, bar_height)
        pygame.draw.rect(self.screen, (50, 150, 255), mana_rect)

        # Border
        pygame.draw.rect(self.screen, Config.COLOR_TEXT, bg_rect, 2)

        # Text
        mana_text = f"MP: {int(character.mana)}/{int(character.max_mana)}"
        text_surface = self.small_font.render(mana_text, True, Config.COLOR_TEXT)
        text_rect = text_surface.get_rect(center=(x + bar_width // 2, y + bar_height // 2))
        self.screen.blit(text_surface, text_rect)

    def render_inventory_panel(self, character: Character, mouse_pos: Tuple[int, int]):
        """Render inventory panel at bottom of screen"""
        # Panel background
        panel_rect = pygame.Rect(
            Config.INVENTORY_PANEL_X,
            Config.INVENTORY_PANEL_Y,
            Config.INVENTORY_PANEL_WIDTH,
            Config.INVENTORY_PANEL_HEIGHT
        )
        pygame.draw.rect(self.screen, Config.COLOR_UI_BG, panel_rect)

        # Title
        self.render_text("INVENTORY", 20, Config.INVENTORY_PANEL_Y + 10, bold=True)

        # Calculate slot positions
        start_x = 20
        start_y = Config.INVENTORY_PANEL_Y + 50
        slot_size = Config.INVENTORY_SLOT_SIZE
        spacing = 5
        slots_per_row = Config.INVENTORY_SLOTS_PER_ROW

        hovered_slot = None

        # Render inventory slots
        for i, item_stack in enumerate(character.inventory.slots):
            row = i // slots_per_row
            col = i % slots_per_row

            x = start_x + col * (slot_size + spacing)
            y = start_y + row * (slot_size + spacing)

            slot_rect = pygame.Rect(x, y, slot_size, slot_size)

            # Check if mouse is over this slot
            is_hovered = slot_rect.collidepoint(mouse_pos)
            if is_hovered and item_stack:
                hovered_slot = (i, item_stack, slot_rect)

            # Draw slot background
            if item_stack:
                pygame.draw.rect(self.screen, Config.COLOR_SLOT_FILLED, slot_rect)
            else:
                pygame.draw.rect(self.screen, Config.COLOR_SLOT_EMPTY, slot_rect)

            # Draw slot border
            border_color = Config.COLOR_SLOT_SELECTED if is_hovered else Config.COLOR_SLOT_BORDER
            pygame.draw.rect(self.screen, border_color, slot_rect, 2)

            # Draw item if present
            if item_stack and i != character.inventory.dragging_slot:
                self.render_item_in_slot(item_stack, slot_rect)

        # Draw dragging item
        if character.inventory.dragging_stack:
            drag_rect = pygame.Rect(
                mouse_pos[0] - slot_size // 2,
                mouse_pos[1] - slot_size // 2,
                slot_size,
                slot_size
            )
            pygame.draw.rect(self.screen, Config.COLOR_SLOT_FILLED, drag_rect)
            pygame.draw.rect(self.screen, Config.COLOR_SLOT_SELECTED, drag_rect, 3)
            self.render_item_in_slot(character.inventory.dragging_stack, drag_rect)

        # Draw tooltip for hovered item
        if hovered_slot and not character.inventory.dragging_stack:
            slot_idx, item_stack, slot_rect = hovered_slot
            self.render_item_tooltip(item_stack, mouse_pos)

    def render_item_in_slot(self, item_stack: ItemStack, rect: pygame.Rect):
        """Render item icon and quantity in inventory slot"""
        mat = item_stack.get_material()

        if mat:
            # Get rarity color
            rarity_color = Config.RARITY_COLORS.get(mat.rarity, (200, 200, 200))

            # Draw colored square for now (placeholder for icons)
            inner_rect = pygame.Rect(
                rect.x + 5,
                rect.y + 5,
                rect.width - 10,
                rect.height - 10
            )
            pygame.draw.rect(self.screen, rarity_color, inner_rect)

            # Draw tier badge
            tier_text = f"T{mat.tier}"
            tier_surface = self.small_font.render(tier_text, True, (0, 0, 0))
            self.screen.blit(tier_surface, (rect.x + 6, rect.y + 6))

        # Draw quantity
        if item_stack.quantity > 1:
            qty_text = str(item_stack.quantity)
            qty_surface = self.small_font.render(qty_text, True, (255, 255, 255))
            qty_rect = qty_surface.get_rect(bottomright=(rect.right - 3, rect.bottom - 3))

            # Black outline for readability
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                outline_rect = qty_rect.copy()
                outline_rect.x += dx
                outline_rect.y += dy
                outline_surface = self.small_font.render(qty_text, True, (0, 0, 0))
                self.screen.blit(outline_surface, outline_rect)

            self.screen.blit(qty_surface, qty_rect)

    def render_item_tooltip(self, item_stack: ItemStack, mouse_pos: Tuple[int, int]):
        """Render tooltip for item"""
        mat = item_stack.get_material()
        if not mat:
            return

        # Tooltip dimensions
        tooltip_width = 250
        tooltip_height = 120
        padding = 10

        # Position tooltip near mouse
        x = mouse_pos[0] + 15
        y = mouse_pos[1] + 15

        # Keep tooltip on screen
        if x + tooltip_width > Config.SCREEN_WIDTH:
            x = mouse_pos[0] - tooltip_width - 15
        if y + tooltip_height > Config.SCREEN_HEIGHT:
            y = mouse_pos[1] - tooltip_height - 15

        # Create semi-transparent background
        tooltip_surface = pygame.Surface((tooltip_width, tooltip_height), pygame.SRCALPHA)
        tooltip_surface.fill(Config.COLOR_TOOLTIP_BG)

        # Render tooltip on separate surface
        temp_screen = tooltip_surface
        y_pos = padding

        # Item name with rarity color
        rarity_color = Config.RARITY_COLORS.get(mat.rarity, (200, 200, 200))
        name_surface = self.font.render(mat.name, True, rarity_color)
        temp_screen.blit(name_surface, (padding, y_pos))
        y_pos += 25

        # Tier and category
        info_text = f"Tier {mat.tier} | {mat.category.capitalize()}"
        info_surface = self.small_font.render(info_text, True, (180, 180, 180))
        temp_screen.blit(info_surface, (padding, y_pos))
        y_pos += 20

        # Rarity
        rarity_text = f"Rarity: {mat.rarity.capitalize()}"
        rarity_surface = self.small_font.render(rarity_text, True, rarity_color)
        temp_screen.blit(rarity_surface, (padding, y_pos))
        y_pos += 25

        # Description (word wrap)
        if mat.description:
            words = mat.description.split()
            line = ""
            for word in words:
                test_line = line + word + " "
                if self.small_font.size(test_line)[0] <= tooltip_width - 2 * padding:
                    line = test_line
                else:
                    if line:
                        desc_surface = self.small_font.render(line, True, (200, 200, 200))
                        temp_screen.blit(desc_surface, (padding, y_pos))
                        y_pos += 18
                    line = word + " "

            if line:
                desc_surface = self.small_font.render(line, True, (200, 200, 200))
                temp_screen.blit(desc_surface, (padding, y_pos))

        # Blit tooltip to main screen
        self.screen.blit(tooltip_surface, (x, y))

    def render_crafting_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        """Render crafting UI window"""
        if not character.crafting_ui_open or not character.active_station:
            return

        recipe_db = RecipeDatabase.get_instance()
        mat_db = MaterialDatabase.get_instance()

        # Window dimensions
        window_width = 800
        window_height = 500
        window_x = (Config.VIEWPORT_WIDTH - window_width) // 2
        window_y = (Config.VIEWPORT_HEIGHT - window_height) // 2

        # Semi-transparent background
        window_surface = pygame.Surface((window_width, window_height), pygame.SRCALPHA)
        window_surface.fill((20, 20, 30, 240))

        # Station header
        station_name = character.active_station.station_type.value.upper()
        header_text = f"{station_name} STATION (T{character.active_station.tier})"
        header_surface = self.font.render(header_text, True, character.active_station.get_color())
        window_surface.blit(header_surface, (20, 20))

        # Close button hint
        close_hint = "[ESC] Close"
        close_surface = self.small_font.render(close_hint, True, (180, 180, 180))
        window_surface.blit(close_surface, (window_width - 120, 20))

        # Get available recipes
        recipes = recipe_db.get_recipes_for_station(
            character.active_station.station_type.value,
            character.active_station.tier
        )

        if not recipes:
            no_recipe_text = "No recipes available for this station."
            no_recipe_surface = self.font.render(no_recipe_text, True, (200, 200, 200))
            window_surface.blit(no_recipe_surface, (20, 80))
        else:
            # Recipe list
            y_offset = 70
            for i, recipe in enumerate(recipes[:5]):  # Show first 5 recipes
                # Recipe button background
                button_rect = pygame.Rect(20, y_offset, window_width - 40, 70)

                # Check if can craft
                can_craft = recipe_db.can_craft(recipe, character.inventory)
                button_color = (40, 60, 40) if can_craft else (60, 40, 40)

                pygame.draw.rect(window_surface, button_color, button_rect)
                pygame.draw.rect(window_surface, (100, 100, 100), button_rect, 2)

                # Output item
                output_mat = mat_db.get_material(recipe.output_id)
                output_name = output_mat.name if output_mat else recipe.output_id
                rarity_color = Config.RARITY_COLORS.get(output_mat.rarity, (200, 200, 200)) if output_mat else (
                200, 200, 200)

                output_text = f"{output_name} x{recipe.output_qty}"
                output_surface = self.font.render(output_text, True, rarity_color)
                window_surface.blit(output_surface, (button_rect.x + 10, button_rect.y + 10))

                # Requirements
                req_y = button_rect.y + 35
                for input_mat in recipe.inputs[:3]:  # Show first 3 inputs
                    mat_id = input_mat.get('materialId', '')
                    required = input_mat.get('quantity', 0)
                    available = character.inventory.get_item_count(mat_id)

                    mat = mat_db.get_material(mat_id)
                    mat_name = mat.name if mat else mat_id

                    has_enough = available >= required
                    req_color = (100, 255, 100) if has_enough else (255, 100, 100)

                    req_text = f"{mat_name}: {available}/{required}"
                    req_surface = self.small_font.render(req_text, True, req_color)
                    window_surface.blit(req_surface, (button_rect.x + 20, req_y))
                    req_y += 18

                # Craft button
                if can_craft:
                    craft_text = "[CLICK] Craft"
                    craft_surface = self.small_font.render(craft_text, True, (100, 255, 100))
                    window_surface.blit(craft_surface, (button_rect.right - 120, button_rect.centery - 8))

                y_offset += 80

        # Blit window to screen
        self.screen.blit(window_surface, (window_x, window_y))

        # Store window rect for click detection
        return pygame.Rect(window_x, window_y, window_width, window_height), recipes[:5] if recipes else []

    def render_stats_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        """Render character stats/progression UI"""
        if not character.stats_ui_open:
            return

        # Window dimensions
        window_width = 900
        window_height = 700
        window_x = (Config.VIEWPORT_WIDTH - window_width) // 2
        window_y = 50

        # Semi-transparent background
        window_surface = pygame.Surface((window_width, window_height), pygame.SRCALPHA)
        window_surface.fill((20, 20, 30, 240))

        # Title
        header_text = f"CHARACTER PROGRESSION - Level {character.leveling.level}"
        header_surface = self.font.render(header_text, True, (255, 215, 0))
        window_surface.blit(header_surface, (20, 20))

        # Close hint
        close_hint = "[C or ESC] Close"
        close_surface = self.small_font.render(close_hint, True, (180, 180, 180))
        window_surface.blit(close_surface, (window_width - 150, 20))

        # Three columns: Stats | Skills | Titles
        col1_x = 20
        col2_x = 320
        col3_x = 620
        y_start = 70

        # === COLUMN 1: STATS ===
        y = y_start
        stats_title = self.font.render("STATS", True, (255, 255, 255))
        window_surface.blit(stats_title, (col1_x, y))
        y += 35

        # Unallocated points
        if character.leveling.unallocated_stat_points > 0:
            points_text = f"Points Available: {character.leveling.unallocated_stat_points}"
            points_surface = self.small_font.render(points_text, True, (0, 255, 0))
            window_surface.blit(points_surface, (col1_x, y))
            y += 25

        # Stats display
        stat_names = ['strength', 'defense', 'vitality', 'luck', 'agility', 'intelligence']
        stat_labels = ['STR', 'DEF', 'VIT', 'LCK', 'AGI', 'INT']

        for stat_name, label in zip(stat_names, stat_labels):
            value = getattr(character.stats, stat_name)
            bonus = character.stats.get_bonus(stat_name)

            stat_text = f"{label}: {value} (+{bonus * 100:.0f}%)"
            stat_surface = self.small_font.render(stat_text, True, (200, 200, 200))
            window_surface.blit(stat_surface, (col1_x, y))

            # +1 button if points available
            if character.leveling.unallocated_stat_points > 0:
                button_rect = pygame.Rect(col1_x + 150, y - 2, 40, 20)
                pygame.draw.rect(window_surface, (50, 100, 50), button_rect)
                pygame.draw.rect(window_surface, (100, 200, 100), button_rect, 2)

                plus_text = self.small_font.render("+1", True, (255, 255, 255))
                plus_rect = plus_text.get_rect(center=button_rect.center)
                window_surface.blit(plus_text, plus_rect)

            y += 28

        y += 20

        # Derived stats
        derived_title = self.small_font.render("Derived Stats:", True, (150, 150, 150))
        window_surface.blit(derived_title, (col1_x, y))
        y += 22

        derived_stats = [
            f"HP: {int(character.max_health)}",
            f"MP: {int(character.max_mana)}",
            f"Carry: {30 + int(character.stats.get_flat_bonus('strength', 'carry_capacity'))} slots"
        ]

        for derived_text in derived_stats:
            derived_surface = self.small_font.render(derived_text, True, (150, 150, 150))
            window_surface.blit(derived_surface, (col1_x + 10, y))
            y += 20

        # === COLUMN 2: SKILLS ===
        y = y_start
        skills_title = self.font.render("SKILLS", True, (255, 255, 255))
        window_surface.blit(skills_title, (col2_x, y))
        y += 35

        # Known skills
        if character.skills.known_skills:
            known_text = f"Known: {len(character.skills.known_skills)}"
            known_surface = self.small_font.render(known_text, True, (200, 200, 200))
            window_surface.blit(known_surface, (col2_x, y))
            y += 25

            # Show first 8 skills
            for i, (skill_id, player_skill) in enumerate(list(character.skills.known_skills.items())[:8]):
                skill_def = player_skill.get_definition()
                if skill_def:
                    # Skill name + level
                    equipped_marker = "★ " if player_skill.is_equipped else "  "
                    skill_text = f"{equipped_marker}{skill_def.name} Lv.{player_skill.level}"
                    color = (255, 215, 0) if player_skill.is_equipped else (180, 180, 180)

                    skill_surface = self.small_font.render(skill_text, True, color)
                    window_surface.blit(skill_surface, (col2_x, y))
                    y += 20
        else:
            no_skills = self.small_font.render("No skills learned yet", True, (150, 150, 150))
            window_surface.blit(no_skills, (col2_x, y))

        # === COLUMN 3: TITLES & CLASS ===
        y = y_start
        titles_title = self.font.render("TITLES & CLASS", True, (255, 255, 255))
        window_surface.blit(titles_title, (col3_x, y))
        y += 35

        # Class
        if character.class_system.current_class:
            class_text = f"Class: {character.class_system.current_class.name}"
            class_surface = self.small_font.render(class_text, True, (100, 200, 255))
            window_surface.blit(class_surface, (col3_x, y))
            y += 25

        # Titles earned
        title_count = len(character.titles.earned_titles)
        titles_count_text = f"Titles Earned: {title_count}"
        titles_count_surface = self.small_font.render(titles_count_text, True, (200, 200, 200))
        window_surface.blit(titles_count_surface, (col3_x, y))
        y += 30

        # List titles
        for title in character.titles.earned_titles[-10:]:  # Show last 10
            title_text = f"• {title.name}"
            title_surface = self.small_font.render(title_text, True, (180, 180, 180))
            window_surface.blit(title_surface, (col3_x, y))
            y += 18

            bonus_text = f"  {title.bonus_description}"
            bonus_surface = self.small_font.render(bonus_text, True, (100, 200, 100))
            window_surface.blit(bonus_surface, (col3_x, y))
            y += 20

        if title_count == 0:
            no_titles = self.small_font.render("No titles yet - keep playing!", True, (150, 150, 150))
            window_surface.blit(no_titles, (col3_x, y))

        # Blit to screen
        self.screen.blit(window_surface, (window_x, window_y))

        return pygame.Rect(window_x, window_y, window_width, window_height)

    def render_health_bar(self, character: Character, x: int, y: int):
        """Render health bar"""
        bar_width = 300
        bar_height = 25

        # Background
        bg_rect = pygame.Rect(x, y, bar_width, bar_height)
        pygame.draw.rect(self.screen, Config.COLOR_HEALTH_BG, bg_rect)

        # Health fill
        health_percent = character.health / character.max_health
        health_width = int(bar_width * health_percent)
        health_rect = pygame.Rect(x, y, health_width, bar_height)
        pygame.draw.rect(self.screen, Config.COLOR_HEALTH, health_rect)

        # Border
        pygame.draw.rect(self.screen, Config.COLOR_TEXT, bg_rect, 2)

        # Text
        health_text = f"HP: {character.health}/{character.max_health}"
        text_surface = self.small_font.render(health_text, True, Config.COLOR_TEXT)
        text_rect = text_surface.get_rect(center=(x + bar_width // 2, y + bar_height // 2))
        self.screen.blit(text_surface, text_rect)

    def render_text(self, text: str, x: int, y: int, bold: bool = False, small: bool = False):
        """Render text"""
        font = self.font if not small else self.small_font
        if bold:
            font.set_bold(True)

        text_surface = font.render(text, True, Config.COLOR_TEXT)
        self.screen.blit(text_surface, (x, y))

        if bold:
            font.set_bold(False)


# ============================================================================
# GAME ENGINE
# ============================================================================
class GameEngine:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT))
        pygame.display.set_caption("2D Game Mockup - Inventory System")
        self.clock = pygame.time.Clock()
        self.running = True

        # Load material database
        print("Loading material database...")
        mat_db = MaterialDatabase.get_instance()

        # Try to find materials JSON (adjust path as needed)
        possible_paths = [
            "data/items-materials-1.JSON",
            "../data/items-materials-1.JSON",
            "../../data/items-materials-1.JSON",
            "Game-1/Definitions.JSON/items-materials-1.JSON",
        ]

        loaded = False
        for path in possible_paths:
            if Path(path).exists():
                mat_db.load_from_file(path)
                loaded = True
                break

        if not loaded:
            print("⚠ Could not find materials JSON, using placeholders")
            mat_db.load_from_file("nonexistent.json")  # Will trigger placeholder creation

        # Load translation database
        print("Loading translation tables...")
        trans_db = TranslationDatabase.get_instance()
        trans_db.load_from_files()

        # Load skill database
        print("Loading skill database...")
        skill_db = SkillDatabase.get_instance()
        skill_db.load_from_file()

        # Load recipe database
        print("Loading recipe database...")
        recipe_db = RecipeDatabase.get_instance()
        recipe_db.load_from_files()

        # Initialize systems
        print("Initializing game systems...")
        self.world = WorldSystem()
        self.character = Character(Position(50.0, 50.0, 0.0))  # Start in center
        self.camera = Camera(Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT)
        self.renderer = Renderer(self.screen)

        # Feedback systems
        self.damage_numbers: List[DamageNumber] = []

        # Crafting UI
        self.crafting_window_rect = None
        self.crafting_recipes = []

        # Stats UI
        self.stats_window_rect = None

        # Input state
        self.keys_pressed = set()
        self.mouse_pos = (0, 0)

        # Delta time tracking
        self.last_tick = pygame.time.get_ticks()

        print("Game initialized successfully!")
        print(f"World size: {Config.WORLD_SIZE}x{Config.WORLD_SIZE}")
        print(f"Starting position: ({self.character.position.x}, {self.character.position.y})")
        print(f"Resources spawned: {len(self.world.resources)}")

    def handle_events(self):
        """Handle input events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.keys_pressed.add(event.key)
                if event.key == pygame.K_ESCAPE:
                    if self.character.crafting_ui_open:
                        self.character.close_crafting_ui()
                    elif self.character.stats_ui_open:
                        self.character.toggle_stats_ui()
                    else:
                        self.running = False
                elif event.key == pygame.K_TAB:
                    self.character.switch_tool()
                elif event.key == pygame.K_c:
                    self.character.toggle_stats_ui()
            elif event.type == pygame.KEYUP:
                if event.key in self.keys_pressed:
                    self.keys_pressed.remove(event.key)
            elif event.type == pygame.MOUSEMOTION:
                self.mouse_pos = event.pos
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    self.handle_mouse_click(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:  # Left release
                    self.handle_mouse_release(event.pos)

    def handle_mouse_click(self, mouse_pos: Tuple[int, int]):
        """Handle left click for harvesting, stations, inventory drag, or UI"""
        # Check if clicking in stats UI
        if self.character.stats_ui_open and self.stats_window_rect:
            if self.stats_window_rect.collidepoint(mouse_pos):
                self.handle_stats_ui_click(mouse_pos)
                return

        # Check if clicking in crafting UI
        if self.character.crafting_ui_open and self.crafting_window_rect:
            if self.crafting_window_rect.collidepoint(mouse_pos):
                # Check if clicking on a recipe
                self.handle_craft_click(mouse_pos)
                return

        # Check if clicking in inventory area
        if mouse_pos[1] >= Config.INVENTORY_PANEL_Y:
            # Calculate which inventory slot was clicked
            start_x = 20
            start_y = Config.INVENTORY_PANEL_Y + 50
            slot_size = Config.INVENTORY_SLOT_SIZE
            spacing = 5

            rel_x = mouse_pos[0] - start_x
            rel_y = mouse_pos[1] - start_y

            if rel_x >= 0 and rel_y >= 0:
                col = rel_x // (slot_size + spacing)
                row = rel_y // (slot_size + spacing)

                # Check if click is actually inside slot (not in spacing)
                in_slot_x = rel_x % (slot_size + spacing) < slot_size
                in_slot_y = rel_y % (slot_size + spacing) < slot_size

                if in_slot_x and in_slot_y:
                    slot_idx = row * Config.INVENTORY_SLOTS_PER_ROW + col
                    if 0 <= slot_idx < self.character.inventory.max_slots:
                        # Only start drag if slot has an item
                        if self.character.inventory.slots[slot_idx] is not None:
                            self.character.inventory.start_drag(slot_idx)
            return

        # Otherwise, try to interact with world (only in viewport area)
        if mouse_pos[0] >= Config.VIEWPORT_WIDTH:
            return

        # Convert screen position to world position
        world_x = (mouse_pos[0] - Config.VIEWPORT_WIDTH // 2) / Config.TILE_SIZE + self.camera.position.x
        world_y = (mouse_pos[1] - Config.VIEWPORT_HEIGHT // 2) / Config.TILE_SIZE + self.camera.position.y
        world_pos = Position(world_x, world_y, 0)

        # Try to interact with crafting station first
        station = self.world.get_station_at(world_pos)
        if station:
            self.character.interact_with_station(station)
            return

        # Try to get resource at clicked position
        resource = self.world.get_resource_at(world_pos)

        if resource:
            # Try to harvest
            result = self.character.harvest_resource(resource)

            if result:
                loot, actual_damage, is_crit = result

                # Create damage number with actual values
                dmg_num = DamageNumber(
                    damage=actual_damage,
                    position=resource.position.copy(),
                    is_crit=is_crit
                )
                self.damage_numbers.append(dmg_num)

                if loot:
                    print(f"Harvested: {loot}")

    def handle_stats_ui_click(self, mouse_pos: Tuple[int, int]):
        """Handle clicking in stats UI"""
        if not self.stats_window_rect:
            return

        # Calculate relative position
        window_x = (Config.VIEWPORT_WIDTH - 900) // 2
        window_y = 50
        rel_x = mouse_pos[0] - window_x
        rel_y = mouse_pos[1] - window_y

        # Check if clicking on +1 buttons
        if self.character.leveling.unallocated_stat_points > 0:
            col1_x = 20
            y_start = 70 + 60  # After title and unallocated points text

            stat_names = ['strength', 'defense', 'vitality', 'luck', 'agility', 'intelligence']

            for i, stat_name in enumerate(stat_names):
                button_x = col1_x + 150
                button_y = y_start + (i * 28)
                button_rect = pygame.Rect(button_x, button_y - 2, 40, 20)

                if button_rect.collidepoint(rel_x, rel_y):
                    # Allocate stat point
                    if self.character.allocate_stat_point(stat_name):
                        print(f"✓ Allocated 1 point to {stat_name.upper()}")
                    break

    def handle_craft_click(self, mouse_pos: Tuple[int, int]):
        """Handle clicking on a craft button"""
        if not self.crafting_window_rect or not self.crafting_recipes:
            return

        # Calculate relative position within window
        rel_x = mouse_pos[0] - self.crafting_window_rect.x
        rel_y = mouse_pos[1] - self.crafting_window_rect.y

        # Check which recipe button was clicked (starting at y=70, 80px tall each)
        button_y_start = 70
        button_height = 80

        for i, recipe in enumerate(self.crafting_recipes):
            button_top = button_y_start + (i * button_height)
            button_bottom = button_top + 70

            if button_top <= rel_y <= button_bottom:
                # Clicked on this recipe
                self.craft_item(recipe)
                break

    def craft_item(self, recipe: Recipe):
        """Craft an item"""
        recipe_db = RecipeDatabase.get_instance()

        # Check if can craft
        if not recipe_db.can_craft(recipe, self.character.inventory):
            print(f"⚠ Not enough materials to craft {recipe.output_id}")
            return

        # Show placeholder mini-game message
        mini_game_messages = {
            "smithing": "🔨 SMITHING MINI-GAME (Grid Placement)",
            "alchemy": "⚗️ ALCHEMY MINI-GAME (Sequential Timing)",
            "refining": "🔥 REFINING MINI-GAME (Hub-Spoke Pattern)",
            "engineering": "🔧 ENGINEERING MINI-GAME (Slot Puzzle)",
            "adornments": "✨ ENCHANTING MINI-GAME (Pattern Creation)"
        }

        message = mini_game_messages.get(recipe.station_type, f"🎮 {recipe.station_type.upper()} MINI-GAME")
        print(f"\n{message}")
        print(f"Crafting: {recipe.output_id} x{recipe.output_qty}")
        print("(Mini-game skipped - instant craft)")

        # Consume materials
        if recipe_db.consume_materials(recipe, self.character.inventory):
            # Add output to inventory
            self.character.inventory.add_item(recipe.output_id, recipe.output_qty)
            print(f"✓ Crafted {recipe.output_id} x{recipe.output_qty}!")
        else:
            print(f"✗ Crafting failed")

    def handle_mouse_release(self, mouse_pos: Tuple[int, int]):
        """Handle mouse release for inventory drag end"""
        if self.character.inventory.dragging_stack:
            # Check if releasing in inventory area
            if mouse_pos[1] >= Config.INVENTORY_PANEL_Y:
                # Calculate which slot
                start_x = 20
                start_y = Config.INVENTORY_PANEL_Y + 50
                slot_size = Config.INVENTORY_SLOT_SIZE
                spacing = 5

                rel_x = mouse_pos[0] - start_x
                rel_y = mouse_pos[1] - start_y

                if rel_x >= 0 and rel_y >= 0:
                    col = rel_x // (slot_size + spacing)
                    row = rel_y // (slot_size + spacing)

                    in_slot_x = rel_x % (slot_size + spacing) < slot_size
                    in_slot_y = rel_y % (slot_size + spacing) < slot_size

                    if in_slot_x and in_slot_y:
                        slot_idx = row * Config.INVENTORY_SLOTS_PER_ROW + col
                        if 0 <= slot_idx < self.character.inventory.max_slots:
                            self.character.inventory.end_drag(slot_idx)
                            return

            # If not released in valid slot, cancel drag
            self.character.inventory.cancel_drag()

    def update(self):
        """Update game state"""
        # Calculate delta time
        current_tick = pygame.time.get_ticks()
        dt = (current_tick - self.last_tick) / 1000.0  # Convert to seconds
        self.last_tick = current_tick

        # Handle movement
        dx, dy = 0, 0

        if pygame.K_w in self.keys_pressed:
            dy -= self.character.movement_speed
        if pygame.K_s in self.keys_pressed:
            dy += self.character.movement_speed
        if pygame.K_a in self.keys_pressed:
            dx -= self.character.movement_speed
        if pygame.K_d in self.keys_pressed:
            dx += self.character.movement_speed

        # Normalize diagonal movement
        if dx != 0 and dy != 0:
            factor = 0.7071  # 1/sqrt(2)
            dx *= factor
            dy *= factor

        # Move character
        if dx != 0 or dy != 0:
            self.character.move(dx, dy, self.world)

        # Camera follows player
        self.camera.follow(self.character.position)

        # Update world (resource respawns)
        self.world.update(dt)

        # Update damage numbers
        self.damage_numbers = [dmg for dmg in self.damage_numbers if dmg.update(dt)]

    def render(self):
        """Render everything"""
        self.screen.fill(Config.COLOR_BACKGROUND)

        # Render world and character
        self.renderer.render_world(self.world, self.camera, self.character, self.damage_numbers)

        # Render UI
        self.renderer.render_ui(self.character, self.mouse_pos)

        # Render inventory panel
        self.renderer.render_inventory_panel(self.character, self.mouse_pos)

        # Render crafting UI if open
        if self.character.crafting_ui_open:
            result = self.renderer.render_crafting_ui(self.character, self.mouse_pos)
            if result:
                self.crafting_window_rect, self.crafting_recipes = result
        else:
            self.crafting_window_rect = None
            self.crafting_recipes = []

        # Render stats UI if open
        if self.character.stats_ui_open:
            self.stats_window_rect = self.renderer.render_stats_ui(self.character, self.mouse_pos)
        else:
            self.stats_window_rect = None

        # Update display
        pygame.display.flip()

    def run(self):
        """Main game loop"""
        print("\n=== GAME STARTED ===")
        print("Controls:")
        print("  WASD - Move character")
        print("  LEFT CLICK - Harvest resource / Interact with station / Craft item")
        print("  DRAG - Move items in inventory")
        print("  TAB - Switch tool")
        print("  C - Open Character Stats (allocate points, view skills & titles)")
        print("  ESC - Close UI / Quit")
        print("\nProgression:")
        print("  🎯 Earn EXP from gathering and crafting to level up")
        print("  📊 Allocate stat points (STR/DEF/VIT/LCK/AGI/INT)")
        print("  🏆 Unlock titles by reaching activity milestones")
        print("  ⚡ Skills and classes coming in future updates")
        print("\nCrafting Stations:")
        print("  🔨 Red Diamond = Smithing")
        print("  ⚗️ Green Diamond = Alchemy")
        print("  🔥 Orange Diamond = Refining")
        print("  🔧 Blue Diamond = Engineering")
        print("  ✨ Purple Diamond = Enchanting/Adornments")
        print("=" * 50 + "\n")

        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(Config.FPS)

        pygame.quit()
        sys.exit()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    game = GameEngine()
    game.run()
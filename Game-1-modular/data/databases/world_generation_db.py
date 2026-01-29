"""World Generation Configuration Database

Loads and provides access to world generation settings from JSON.
Follows the singleton pattern used by other database classes.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from core.paths import get_resource_path


@dataclass
class ChunkLoadingConfig:
    """Configuration for chunk loading behavior."""
    load_radius: int = 4
    spawn_always_loaded_radius: int = 1
    chunk_size: int = 16


@dataclass
class BiomeDistributionConfig:
    """Configuration for biome type distribution."""
    water: float = 0.10
    forest: float = 0.50
    cave: float = 0.40

    def validate(self) -> bool:
        """Validate that distributions sum to 1.0."""
        total = self.water + self.forest + self.cave
        return abs(total - 1.0) < 0.001


@dataclass
class BiomeClusteringConfig:
    """Configuration for biome clustering/noise."""
    biome_noise_scale: float = 4.0
    biome_noise_octaves: int = 3
    danger_noise_scale: float = 6.0


@dataclass
class DangerDistribution:
    """Distribution of danger levels in a zone."""
    peaceful: float = 0.5
    dangerous: float = 0.4
    rare: float = 0.1


@dataclass
class DangerZonesConfig:
    """Configuration for danger zone system."""
    safe_zone_radius: int = 2
    transition_zone_radius: int = 10
    max_danger_enabled: bool = True
    safe_zone_distribution: DangerDistribution = field(default_factory=lambda: DangerDistribution(1.0, 0.0, 0.0))
    transition_zone_distribution: DangerDistribution = field(default_factory=lambda: DangerDistribution(0.4, 0.5, 0.1))
    outer_zone_distribution: DangerDistribution = field(default_factory=lambda: DangerDistribution(0.2, 0.5, 0.3))


@dataclass
class ResourceSpawnConfig:
    """Configuration for resource spawning in a chunk type."""
    min_resources: int
    max_resources: int
    tier_range: Tuple[int, int]


@dataclass
class ResourceSpawningConfig:
    """Configuration for all resource spawning."""
    peaceful_chunks: ResourceSpawnConfig = field(default_factory=lambda: ResourceSpawnConfig(3, 6, (1, 2)))
    dangerous_chunks: ResourceSpawnConfig = field(default_factory=lambda: ResourceSpawnConfig(5, 8, (2, 3)))
    rare_chunks: ResourceSpawnConfig = field(default_factory=lambda: ResourceSpawnConfig(6, 10, (3, 4)))


@dataclass
class FishingSpotConfig:
    """Configuration for fishing spots in water chunks."""
    min_spots: int
    max_spots: int
    tier_range: Tuple[int, int]


@dataclass
class WaterChunksConfig:
    """Configuration for water chunk generation."""
    normal_water: FishingSpotConfig = field(default_factory=lambda: FishingSpotConfig(3, 6, (1, 2)))
    cursed_swamp: FishingSpotConfig = field(default_factory=lambda: FishingSpotConfig(5, 8, (3, 4)))
    lake_chance: float = 0.45
    river_chance: float = 0.45
    cursed_swamp_chance: float = 0.10


@dataclass
class DungeonSpawningConfig:
    """Configuration for dungeon entrance spawning."""
    enabled: bool = True
    spawn_chance_per_chunk: float = 0.083
    excluded_in_spawn_area: bool = True
    excluded_in_water: bool = True
    min_distance_from_spawn: int = 2


@dataclass
class SpawnAreaConfig:
    """Configuration for the spawn area."""
    resource_exclusion_radius: int = 8
    crafting_stations_enabled: bool = True


@dataclass
class ChunkUnloadingConfig:
    """Configuration for chunk unloading behavior."""
    enabled: bool = True
    save_modified_chunks: bool = True
    track_unload_time: bool = True


@dataclass
class DebugConfig:
    """Debug settings for world generation."""
    log_chunk_generation: bool = False
    log_biome_assignments: bool = False
    log_dungeon_spawns: bool = True
    show_seed_on_f1: bool = True


class WorldGenerationConfig:
    """Singleton configuration loader for world generation settings.

    Loads settings from Definitions.JSON/world_generation.JSON and provides
    typed access to all configuration values.

    Usage:
        config = WorldGenerationConfig.get_instance()
        load_radius = config.chunk_loading.load_radius
        water_ratio = config.biome_distribution.water
    """

    _instance: Optional['WorldGenerationConfig'] = None
    _loaded: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not WorldGenerationConfig._loaded:
            self._init_defaults()
            self._load_config()
            WorldGenerationConfig._loaded = True

    @classmethod
    def get_instance(cls) -> 'WorldGenerationConfig':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reload(cls) -> 'WorldGenerationConfig':
        """Force reload configuration from JSON."""
        cls._loaded = False
        cls._instance = None
        return cls.get_instance()

    def _init_defaults(self):
        """Initialize with default values."""
        self.chunk_loading = ChunkLoadingConfig()
        self.biome_distribution = BiomeDistributionConfig()
        self.biome_clustering = BiomeClusteringConfig()
        self.danger_zones = DangerZonesConfig()
        self.spawn_area = SpawnAreaConfig()
        self.resource_spawning = ResourceSpawningConfig()
        self.water_chunks = WaterChunksConfig()
        self.dungeon_spawning = DungeonSpawningConfig()
        self.chunk_unloading = ChunkUnloadingConfig()
        self.debug = DebugConfig()
        self.loaded_from_file = False

    def _load_config(self):
        """Load configuration from JSON file."""
        config_path = get_resource_path("Definitions.JSON/world_generation.JSON")

        if not config_path.exists():
            print(f"World generation config not found at {config_path}, using defaults")
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self._parse_config(data)
            self.loaded_from_file = True
            print(f"Loaded world generation config from {config_path}")

        except json.JSONDecodeError as e:
            print(f"Error parsing world_generation.JSON: {e}")
            print("Using default configuration")
        except Exception as e:
            print(f"Error loading world_generation.JSON: {e}")
            print("Using default configuration")

    def _parse_config(self, data: Dict[str, Any]):
        """Parse configuration data from JSON."""
        # Chunk loading
        if "chunk_loading" in data:
            cl = data["chunk_loading"]
            self.chunk_loading = ChunkLoadingConfig(
                load_radius=cl.get("load_radius", 4),
                spawn_always_loaded_radius=cl.get("spawn_always_loaded_radius", 1),
                chunk_size=cl.get("chunk_size", 16)
            )

        # Biome distribution
        if "biome_distribution" in data:
            bd = data["biome_distribution"]
            self.biome_distribution = BiomeDistributionConfig(
                water=bd.get("water", 0.10),
                forest=bd.get("forest", 0.50),
                cave=bd.get("cave", 0.40)
            )
            if not self.biome_distribution.validate():
                print("Warning: Biome distribution doesn't sum to 1.0, adjusting...")
                total = self.biome_distribution.water + self.biome_distribution.forest + self.biome_distribution.cave
                self.biome_distribution.water /= total
                self.biome_distribution.forest /= total
                self.biome_distribution.cave /= total

        # Biome clustering
        if "biome_clustering" in data:
            bc = data["biome_clustering"]
            self.biome_clustering = BiomeClusteringConfig(
                biome_noise_scale=bc.get("biome_noise_scale", 4.0),
                biome_noise_octaves=bc.get("biome_noise_octaves", 3),
                danger_noise_scale=bc.get("danger_noise_scale", 6.0)
            )

        # Danger zones
        if "danger_zones" in data:
            dz = data["danger_zones"]
            self.danger_zones = DangerZonesConfig(
                safe_zone_radius=dz.get("safe_zone_radius", 2),
                transition_zone_radius=dz.get("transition_zone_radius", 10),
                max_danger_enabled=dz.get("max_danger_enabled", True),
                safe_zone_distribution=self._parse_danger_distribution(
                    dz.get("safe_zone_distribution", {}), DangerDistribution(1.0, 0.0, 0.0)
                ),
                transition_zone_distribution=self._parse_danger_distribution(
                    dz.get("transition_zone_distribution", {}), DangerDistribution(0.4, 0.5, 0.1)
                ),
                outer_zone_distribution=self._parse_danger_distribution(
                    dz.get("outer_zone_distribution", {}), DangerDistribution(0.2, 0.5, 0.3)
                )
            )

        # Spawn area
        if "spawn_area" in data:
            sa = data["spawn_area"]
            self.spawn_area = SpawnAreaConfig(
                resource_exclusion_radius=sa.get("resource_exclusion_radius", 8),
                crafting_stations_enabled=sa.get("crafting_station_area", {}).get("enabled", True)
            )

        # Resource spawning
        if "resource_spawning" in data:
            rs = data["resource_spawning"]
            self.resource_spawning = ResourceSpawningConfig(
                peaceful_chunks=self._parse_resource_spawn(
                    rs.get("peaceful_chunks", {}), ResourceSpawnConfig(3, 6, (1, 2))
                ),
                dangerous_chunks=self._parse_resource_spawn(
                    rs.get("dangerous_chunks", {}), ResourceSpawnConfig(5, 8, (2, 3))
                ),
                rare_chunks=self._parse_resource_spawn(
                    rs.get("rare_chunks", {}), ResourceSpawnConfig(6, 10, (3, 4))
                )
            )

        # Water chunks
        if "water_chunks" in data:
            wc = data["water_chunks"]
            fishing = wc.get("fishing_spots", {})
            subtypes = wc.get("water_subtypes", {})

            # Parse water subtype chances with dilutive normalization
            lake_chance = subtypes.get("lake_chance", 0.45)
            river_chance = subtypes.get("river_chance", 0.45)
            cursed_swamp_chance = subtypes.get("cursed_swamp_chance", 0.10)

            # Normalize if sum != 1.0 (dilutive approach)
            total_water = lake_chance + river_chance + cursed_swamp_chance
            if abs(total_water - 1.0) > 0.001 and total_water > 0:
                lake_chance /= total_water
                river_chance /= total_water
                cursed_swamp_chance /= total_water

            self.water_chunks = WaterChunksConfig(
                normal_water=self._parse_fishing_spots(
                    fishing.get("normal_water", {}), FishingSpotConfig(3, 6, (1, 2))
                ),
                cursed_swamp=self._parse_fishing_spots(
                    fishing.get("cursed_swamp", {}), FishingSpotConfig(5, 8, (3, 4))
                ),
                lake_chance=lake_chance,
                river_chance=river_chance,
                cursed_swamp_chance=cursed_swamp_chance
            )

        # Dungeon spawning
        if "dungeon_spawning" in data:
            ds = data["dungeon_spawning"]
            self.dungeon_spawning = DungeonSpawningConfig(
                enabled=ds.get("enabled", True),
                spawn_chance_per_chunk=ds.get("spawn_chance_per_chunk", 0.083),
                excluded_in_spawn_area=ds.get("excluded_in_spawn_area", True),
                excluded_in_water=ds.get("excluded_in_water", True),
                min_distance_from_spawn=ds.get("min_distance_from_spawn", 2)
            )

        # Chunk unloading
        if "chunk_unloading" in data:
            cu = data["chunk_unloading"]
            self.chunk_unloading = ChunkUnloadingConfig(
                enabled=cu.get("enabled", True),
                save_modified_chunks=cu.get("save_modified_chunks", True),
                track_unload_time=cu.get("track_unload_time", True)
            )

        # Debug
        if "debug" in data:
            db = data["debug"]
            self.debug = DebugConfig(
                log_chunk_generation=db.get("log_chunk_generation", False),
                log_biome_assignments=db.get("log_biome_assignments", False),
                log_dungeon_spawns=db.get("log_dungeon_spawns", True),
                show_seed_on_f1=db.get("show_seed_on_f1", True)
            )

    def _parse_danger_distribution(self, data: Dict[str, Any], default: DangerDistribution) -> DangerDistribution:
        """Parse a danger distribution from JSON with dilutive normalization.

        If values don't sum to 1.0, they are normalized proportionally.
        E.g., peaceful=6, dangerous=3, rare=1 becomes 0.6, 0.3, 0.1
        """
        if not data:
            return default

        peaceful = data.get("peaceful", default.peaceful)
        dangerous = data.get("dangerous", default.dangerous)
        rare = data.get("rare", default.rare)

        # Normalize if sum != 1.0 (dilutive approach)
        total = peaceful + dangerous + rare
        if abs(total - 1.0) > 0.001 and total > 0:
            peaceful /= total
            dangerous /= total
            rare /= total

        return DangerDistribution(
            peaceful=peaceful,
            dangerous=dangerous,
            rare=rare
        )

    def _parse_resource_spawn(self, data: Dict[str, Any], default: ResourceSpawnConfig) -> ResourceSpawnConfig:
        """Parse resource spawn config from JSON."""
        if not data:
            return default
        tier_range = data.get("tier_range", list(default.tier_range))
        return ResourceSpawnConfig(
            min_resources=data.get("min_resources", default.min_resources),
            max_resources=data.get("max_resources", default.max_resources),
            tier_range=(tier_range[0], tier_range[1])
        )

    def _parse_fishing_spots(self, data: Dict[str, Any], default: FishingSpotConfig) -> FishingSpotConfig:
        """Parse fishing spot config from JSON."""
        if not data:
            return default
        tier_range = data.get("tier_range", list(default.tier_range))
        return FishingSpotConfig(
            min_spots=data.get("min_spots", default.min_spots),
            max_spots=data.get("max_spots", default.max_spots),
            tier_range=(tier_range[0], tier_range[1])
        )

    def get_danger_distribution(self, chunk_distance: int) -> DangerDistribution:
        """Get the danger distribution for a chunk at given distance from spawn.

        Args:
            chunk_distance: Chebyshev distance from spawn in chunks

        Returns:
            DangerDistribution for that distance
        """
        if chunk_distance <= self.danger_zones.safe_zone_radius:
            return self.danger_zones.safe_zone_distribution
        elif chunk_distance <= self.danger_zones.transition_zone_radius:
            return self.danger_zones.transition_zone_distribution
        else:
            return self.danger_zones.outer_zone_distribution

    def get_resource_config(self, danger_level: str) -> ResourceSpawnConfig:
        """Get resource spawn config for a danger level.

        Args:
            danger_level: One of "peaceful", "dangerous", "rare"

        Returns:
            ResourceSpawnConfig for that danger level
        """
        if danger_level == "peaceful":
            return self.resource_spawning.peaceful_chunks
        elif danger_level == "dangerous":
            return self.resource_spawning.dangerous_chunks
        else:
            return self.resource_spawning.rare_chunks

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration for debugging."""
        return {
            "loaded_from_file": self.loaded_from_file,
            "chunk_load_radius": self.chunk_loading.load_radius,
            "biome_distribution": {
                "water": f"{self.biome_distribution.water:.0%}",
                "forest": f"{self.biome_distribution.forest:.0%}",
                "cave": f"{self.biome_distribution.cave:.0%}"
            },
            "danger_zones": {
                "safe_zone_radius": self.danger_zones.safe_zone_radius,
                "transition_zone_radius": self.danger_zones.transition_zone_radius,
                "max_danger_capped": self.danger_zones.max_danger_enabled
            },
            "dungeon_spawn_chance": f"{self.dungeon_spawning.spawn_chance_per_chunk:.1%}"
        }

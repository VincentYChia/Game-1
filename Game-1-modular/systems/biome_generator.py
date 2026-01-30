"""Biome generation system for infinite world generation.

Uses deterministic per-chunk random selection to generate consistent biome
assignments for any chunk coordinate, enabling infinite world expansion.

BIOME DISTRIBUTION:
- Each chunk gets a deterministic random roll based on seed + coordinates
- Ratios from config are respected (water/forest/cave)
- Small local clustering via hash-based neighbor tendency

DANGER ZONES:
- Within ±8 chunks of spawn: Progressively safer closer to spawn
- Beyond ±8 chunks: Completely random/fair game (no bias)
"""

import random
from typing import Tuple, Optional, Dict
from enum import Enum

from data.models import ChunkType
from data.databases.world_generation_db import WorldGenerationConfig


class BiomeCategory(Enum):
    """High-level biome categories."""
    WATER = "water"
    FOREST = "forest"
    CAVE = "cave"  # Includes quarries


class BiomeGenerator:
    """Deterministic biome generation using per-chunk random selection.

    Generates consistent chunk types for any coordinate based on a world seed.
    Supports infinite world expansion with controlled distribution ratios.

    Each chunk gets an independent random roll that respects the configured
    ratios (water/forest/cave). A small local influence creates natural
    2-3 chunk clusters without mega-regions.

    Danger Zones:
        - ±8 chunks from spawn: Progressive safety (closer = safer)
        - Beyond ±8 chunks: No bias, random danger distribution

    Usage:
        generator = BiomeGenerator(world_seed=12345)
        chunk_type = generator.get_chunk_type(5, -3)  # Returns ChunkType
    """

    # Safety zone configuration
    SAFE_ZONE_RADIUS = 8  # Chunks - within this, progressively safer toward spawn

    def __init__(self, world_seed: int):
        """Initialize biome generator with world seed.

        Args:
            world_seed: Master seed for deterministic generation
        """
        self.seed = world_seed

        # Load configuration from JSON
        self._config = WorldGenerationConfig.get_instance()

        # Cache frequently accessed config values
        self._water_ratio = self._config.biome_distribution.water
        self._forest_ratio = self._config.biome_distribution.forest
        self._cave_ratio = self._config.biome_distribution.cave

        self._dungeon_spawn_chance = self._config.dungeon_spawning.spawn_chance_per_chunk
        self._dungeon_min_distance = self._config.dungeon_spawning.min_distance_from_spawn

        # Cache for chunk types (to ensure consistency when checking neighbors)
        self._type_cache: Dict[Tuple[int, int], ChunkType] = {}

        # Debug tracking
        self._debug_enabled = self._config.debug.log_biome_assignments
        self._generation_stats = {
            "water": 0, "forest": 0, "cave": 0,
            "peaceful": 0, "dangerous": 0, "rare": 0
        }

        if self._debug_enabled:
            print(f"BiomeGenerator initialized with seed {world_seed}")
            print(f"  Biome distribution: water={self._water_ratio:.0%}, forest={self._forest_ratio:.0%}, cave={self._cave_ratio:.0%}")
            print(f"  Safe zone radius: {self.SAFE_ZONE_RADIUS} chunks")

    def get_chunk_seed(self, chunk_x: int, chunk_y: int) -> int:
        """Derive a deterministic seed for a specific chunk.

        Uses Szudzik's pairing function for unique coordinate hashing,
        extended to handle negative coordinates.

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            Deterministic seed unique to this chunk and world seed
        """
        # Handle negative coordinates by mapping to positive space
        ax = chunk_x * 2 if chunk_x >= 0 else (-chunk_x * 2) - 1
        ay = chunk_y * 2 if chunk_y >= 0 else (-chunk_y * 2) - 1

        # Szudzik's pairing function
        if ax >= ay:
            coord_hash = ax * ax + ax + ay
        else:
            coord_hash = ay * ay + ax

        # Combine with world seed using mixing
        h = self.seed
        h ^= coord_hash
        h = (h ^ (h >> 16)) * 0x85ebca6b
        h = (h ^ (h >> 13)) * 0xc2b2ae35
        h = h ^ (h >> 16)

        return h & 0xFFFFFFFF

    def _hash_2d(self, x: int, y: int, offset: int = 0) -> float:
        """Generate a pseudo-random float [0, 1) for 2D coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
            offset: Optional offset for multiple independent values

        Returns:
            Deterministic float in [0, 1)
        """
        # Mix coordinates with seed
        h = self.seed + offset
        h ^= x * 374761393
        h ^= y * 668265263
        h = (h ^ (h >> 13)) * 1274126177
        h ^= (h >> 16)

        return (h & 0x7FFFFFFF) / 0x7FFFFFFF

    def _smoothstep(self, t: float) -> float:
        """Smoothstep interpolation for smoother noise."""
        return t * t * (3 - 2 * t)

    def _noise_2d(self, x: float, y: float, offset: int = 0) -> float:
        """2D value noise with smooth interpolation.

        Args:
            x: X coordinate (can be fractional)
            y: Y coordinate (can be fractional)
            offset: Seed offset for independent noise layers

        Returns:
            Noise value in [-1, 1]
        """
        # Grid cell coordinates
        x0, y0 = int(x) if x >= 0 else int(x) - 1, int(y) if y >= 0 else int(y) - 1
        x1, y1 = x0 + 1, y0 + 1

        # Interpolation weights
        sx = self._smoothstep(x - x0)
        sy = self._smoothstep(y - y0)

        # Corner values
        n00 = self._hash_2d(x0, y0, offset) * 2 - 1
        n10 = self._hash_2d(x1, y0, offset) * 2 - 1
        n01 = self._hash_2d(x0, y1, offset) * 2 - 1
        n11 = self._hash_2d(x1, y1, offset) * 2 - 1

        # Bilinear interpolation
        nx0 = n00 * (1 - sx) + n10 * sx
        nx1 = n01 * (1 - sx) + n11 * sx

        return nx0 * (1 - sy) + nx1 * sy

    def _fractal_noise(self, x: float, y: float, octaves: int = 2,
                       scale: float = 1.0, offset: int = 0) -> float:
        """Multi-octave fractal noise for organic patterns.

        Args:
            x: X coordinate
            y: Y coordinate
            octaves: Number of noise layers
            scale: Base scale factor
            offset: Seed offset

        Returns:
            Fractal noise value roughly in [-1, 1]
        """
        total = 0.0
        amplitude = 1.0
        frequency = 1.0 / scale
        max_value = 0.0

        for i in range(octaves):
            total += self._noise_2d(x * frequency, y * frequency, offset + i * 1000) * amplitude
            max_value += amplitude
            amplitude *= 0.5
            frequency *= 2.0

        return total / max_value

    def _get_biome_category(self, chunk_x: int, chunk_y: int) -> BiomeCategory:
        """Determine the high-level biome category for a chunk.

        Uses per-chunk random selection based on configured ratios.
        Each chunk gets an independent roll, ensuring correct global distribution.

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            BiomeCategory for this chunk
        """
        # Get deterministic random value for this chunk
        roll = self._hash_2d(chunk_x, chunk_y, offset=100)

        # Select category based on configured ratios
        # roll is uniform [0, 1), so this respects the ratios exactly
        if roll < self._water_ratio:
            return BiomeCategory.WATER
        elif roll < self._water_ratio + self._forest_ratio:
            return BiomeCategory.FOREST
        else:
            return BiomeCategory.CAVE

    def _get_type_cluster_value(self, chunk_x: int, chunk_y: int) -> float:
        """Get noise value for type clustering within a category.

        Uses noise to create small (2-3 chunk) type clusters for variety
        within biome categories (e.g., caves vs quarries).

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            Noise value in [0, 1] for type selection
        """
        # Use simple hash for variety - creates small natural clusters
        noise = self._hash_2d(chunk_x, chunk_y, offset=3000)
        return noise

    def _get_danger_level(self, chunk_x: int, chunk_y: int) -> str:
        """Determine danger level based on distance from spawn.

        DANGER ZONE SYSTEM:
        - Within ±8 chunks: Progressive safety (closer = safer)
        - Beyond ±8 chunks: Random/fair game (no bias)

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            One of: "peaceful", "dangerous", "rare"
        """
        # Distance from spawn (Chebyshev distance)
        distance = max(abs(chunk_x), abs(chunk_y))

        # Get deterministic random value for this chunk
        roll = self._hash_2d(chunk_x, chunk_y, offset=5000)

        if distance <= self.SAFE_ZONE_RADIUS:
            # SAFE ZONE: Progressive safety toward spawn
            # At distance 0: 100% peaceful
            # At distance 8: roughly 40% peaceful, 45% dangerous, 15% rare
            safety_factor = 1.0 - (distance / self.SAFE_ZONE_RADIUS)

            # Blend between safe distribution and normal distribution
            peaceful_threshold = 0.40 + (0.60 * safety_factor)  # 0.40 to 1.0
            dangerous_threshold = peaceful_threshold + 0.45 * (1 - safety_factor)

            if roll < peaceful_threshold:
                return "peaceful"
            elif roll < dangerous_threshold:
                return "dangerous"
            else:
                return "rare"
        else:
            # OUTER ZONE: Random/fair game - no distance bias
            # Distribution: 40% peaceful, 40% dangerous, 20% rare
            if roll < 0.40:
                return "peaceful"
            elif roll < 0.80:
                return "dangerous"
            else:
                return "rare"

    def _is_spawn_area(self, chunk_x: int, chunk_y: int) -> bool:
        """Check if chunk is in the protected spawn area.

        Uses the spawn_always_loaded_radius from configuration.

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            True if chunk is in spawn area
        """
        spawn_radius = self._config.chunk_loading.spawn_always_loaded_radius
        return abs(chunk_x) <= spawn_radius and abs(chunk_y) <= spawn_radius

    def get_chunk_type(self, chunk_x: int, chunk_y: int) -> ChunkType:
        """Get the chunk type for any coordinate.

        This is the main entry point for chunk type determination.
        Results are deterministic based on world seed and coordinates.

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            ChunkType for this chunk
        """
        # Check cache first
        cache_key = (chunk_x, chunk_y)
        if cache_key in self._type_cache:
            return self._type_cache[cache_key]

        # Spawn area is always peaceful forest/quarry/cave
        if self._is_spawn_area(chunk_x, chunk_y):
            chunk_type = self._get_spawn_area_type(chunk_x, chunk_y)
        else:
            # Get biome category and danger level
            biome = self._get_biome_category(chunk_x, chunk_y)
            danger = self._get_danger_level(chunk_x, chunk_y)

            # Convert to specific chunk type
            chunk_type = self._biome_to_chunk_type(biome, danger, chunk_x, chunk_y)

            # Track stats for debugging
            self._generation_stats[biome.value] += 1
            self._generation_stats[danger] += 1

        # Cache result
        self._type_cache[cache_key] = chunk_type

        if self._debug_enabled:
            print(f"Chunk ({chunk_x}, {chunk_y}): type={chunk_type.value}")

        return chunk_type

    def _get_spawn_area_type(self, chunk_x: int, chunk_y: int) -> ChunkType:
        """Get chunk type for spawn area (always peaceful).

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            A peaceful ChunkType
        """
        # Use chunk seed for deterministic selection
        rng = random.Random(self.get_chunk_seed(chunk_x, chunk_y))

        # Spawn area gets variety of peaceful types
        return rng.choice([
            ChunkType.PEACEFUL_FOREST,
            ChunkType.PEACEFUL_QUARRY,
            ChunkType.PEACEFUL_CAVE
        ])

    def _biome_to_chunk_type(self, biome: BiomeCategory, danger: str,
                             chunk_x: int, chunk_y: int) -> ChunkType:
        """Convert biome category and danger to specific ChunkType.

        Args:
            biome: BiomeCategory (WATER, FOREST, or CAVE)
            danger: Danger level ("peaceful", "dangerous", or "rare")
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            Specific ChunkType
        """
        # Get type value for sub-type selection
        type_roll = self._get_type_cluster_value(chunk_x, chunk_y)

        if biome == BiomeCategory.WATER:
            if danger == "rare":
                return ChunkType.WATER_CURSED_SWAMP
            # Use type_roll for lake/river variety
            lake_chance = self._config.water_chunks.lake_chance
            if type_roll < lake_chance:
                return ChunkType.WATER_LAKE
            else:
                return ChunkType.WATER_RIVER

        elif biome == BiomeCategory.FOREST:
            # Forest type based on danger level
            if danger == "peaceful":
                return ChunkType.PEACEFUL_FOREST
            elif danger == "dangerous":
                return ChunkType.DANGEROUS_FOREST
            else:
                return ChunkType.RARE_HIDDEN_FOREST

        else:  # CAVE (includes quarries)
            # Use type_roll for cave vs quarry variety (50/50)
            is_quarry = type_roll < 0.5

            if danger == "peaceful":
                return ChunkType.PEACEFUL_QUARRY if is_quarry else ChunkType.PEACEFUL_CAVE
            elif danger == "dangerous":
                return ChunkType.DANGEROUS_QUARRY if is_quarry else ChunkType.DANGEROUS_CAVE
            else:
                return ChunkType.RARE_ANCIENT_QUARRY if is_quarry else ChunkType.RARE_DEEP_CAVE

    def is_water_chunk(self, chunk_x: int, chunk_y: int) -> bool:
        """Check if a chunk is a water type.

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            True if chunk is water (lake, river, or swamp)
        """
        # Spawn area is never water
        if self._is_spawn_area(chunk_x, chunk_y):
            return False

        biome = self._get_biome_category(chunk_x, chunk_y)
        return biome == BiomeCategory.WATER

    def should_spawn_dungeon(self, chunk_x: int, chunk_y: int) -> bool:
        """Determine if a dungeon entrance should spawn in this chunk.

        Uses configuration for spawn chance and exclusion rules.

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            True if dungeon should spawn
        """
        # Check if dungeons are enabled
        if not self._config.dungeon_spawning.enabled:
            return False

        # Check minimum distance from spawn
        distance = max(abs(chunk_x), abs(chunk_y))
        if distance < self._dungeon_min_distance:
            return False

        # No dungeons in spawn area (if configured)
        if self._config.dungeon_spawning.excluded_in_spawn_area:
            if self._is_spawn_area(chunk_x, chunk_y):
                return False

        # No dungeons in water chunks (if configured)
        if self._config.dungeon_spawning.excluded_in_water:
            if self.is_water_chunk(chunk_x, chunk_y):
                return False

        # Use deterministic roll based on chunk seed
        roll = self._hash_2d(chunk_x, chunk_y, offset=10000)

        # Check against spawn chance from config
        should_spawn = roll < self._dungeon_spawn_chance

        if should_spawn and self._config.debug.log_dungeon_spawns:
            print(f"Dungeon spawning at chunk ({chunk_x}, {chunk_y})")

        return should_spawn

    def get_biome_debug_info(self, chunk_x: int, chunk_y: int) -> dict:
        """Get debug information about biome calculation for a chunk.

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate

        Returns:
            Dictionary with biome calculation details
        """
        biome = self._get_biome_category(chunk_x, chunk_y)
        danger = self._get_danger_level(chunk_x, chunk_y)
        chunk_type = self.get_chunk_type(chunk_x, chunk_y)
        distance = max(abs(chunk_x), abs(chunk_y))

        # Determine which zone the chunk is in
        if distance <= self._config.chunk_loading.spawn_always_loaded_radius:
            zone = "spawn"
        elif distance <= self.SAFE_ZONE_RADIUS:
            zone = "safe"
        else:
            zone = "outer"

        return {
            "chunk_coords": (chunk_x, chunk_y),
            "chunk_seed": self.get_chunk_seed(chunk_x, chunk_y),
            "biome_category": biome.value,
            "danger_level": danger,
            "danger_zone": zone,
            "chunk_type": chunk_type.value,
            "is_spawn_area": self._is_spawn_area(chunk_x, chunk_y),
            "is_water": self.is_water_chunk(chunk_x, chunk_y),
            "has_dungeon": self.should_spawn_dungeon(chunk_x, chunk_y),
            "distance_from_spawn": distance,
            "biome_roll": self._hash_2d(chunk_x, chunk_y, offset=100),
            "danger_roll": self._hash_2d(chunk_x, chunk_y, offset=5000),
            "type_roll": self._get_type_cluster_value(chunk_x, chunk_y),
            "config_summary": self._config.get_summary()
        }

    def get_generation_stats(self) -> dict:
        """Get statistics about generated chunks.

        Returns:
            Dictionary with counts of each biome and danger level
        """
        total_biome = self._generation_stats["water"] + self._generation_stats["forest"] + self._generation_stats["cave"]
        total_danger = self._generation_stats["peaceful"] + self._generation_stats["dangerous"] + self._generation_stats["rare"]

        stats = {
            "counts": dict(self._generation_stats),
            "totals": {"biome": total_biome, "danger": total_danger}
        }

        if total_biome > 0:
            stats["biome_percentages"] = {
                "water": f"{self._generation_stats['water'] / total_biome:.1%}",
                "forest": f"{self._generation_stats['forest'] / total_biome:.1%}",
                "cave": f"{self._generation_stats['cave'] / total_biome:.1%}"
            }

        if total_danger > 0:
            stats["danger_percentages"] = {
                "peaceful": f"{self._generation_stats['peaceful'] / total_danger:.1%}",
                "dangerous": f"{self._generation_stats['dangerous'] / total_danger:.1%}",
                "rare": f"{self._generation_stats['rare'] / total_danger:.1%}"
            }

        return stats

    def print_area_debug(self, center_x: int = 0, center_y: int = 0, radius: int = 5):
        """Print a debug map of biome categories around a center point.

        Args:
            center_x: Center chunk X
            center_y: Center chunk Y
            radius: Radius of area to show
        """
        print(f"\n=== BIOME DEBUG MAP (center: {center_x},{center_y}, radius: {radius}) ===")
        print("Legend: W=Water, F=Forest, C=Cave | lowercase=peaceful, UPPER=dangerous, [X]=rare")
        print()

        # Print column headers
        header = "     "
        for x in range(center_x - radius, center_x + radius + 1):
            header += f"{x:3d}"
        print(header)
        print("     " + "-" * ((radius * 2 + 1) * 3))

        for y in range(center_y - radius, center_y + radius + 1):
            row = f"{y:4d}|"
            for x in range(center_x - radius, center_x + radius + 1):
                biome = self._get_biome_category(x, y)
                danger = self._get_danger_level(x, y)

                # Choose character based on biome
                if biome == BiomeCategory.WATER:
                    char = "W"
                elif biome == BiomeCategory.FOREST:
                    char = "F"
                else:
                    char = "C"

                # Format based on danger
                if danger == "peaceful":
                    cell = f" {char.lower()} "
                elif danger == "dangerous":
                    cell = f" {char} "
                else:  # rare
                    cell = f"[{char}]"

                row += cell
            print(row)

        print()
        print("Stats for this area:")
        # Count biomes in area
        area_stats = {"water": 0, "forest": 0, "cave": 0}
        for y in range(center_y - radius, center_y + radius + 1):
            for x in range(center_x - radius, center_x + radius + 1):
                biome = self._get_biome_category(x, y)
                area_stats[biome.value] += 1

        total = sum(area_stats.values())
        for biome, count in area_stats.items():
            print(f"  {biome}: {count}/{total} ({count/total:.1%})")
        print()

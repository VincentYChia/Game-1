"""Geographic system configuration.

All configurable constants for the world generation pipeline.
Loaded from geography-config.json with sensible defaults.
No values are hardcoded — everything can be overridden via JSON.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple


@dataclass
class WorldConfig:
    """Top-level world parameters."""
    world_size: int = 512       # Chunks per side (512 = 262,144 total chunks)
    chunk_size: int = 16        # Tiles per chunk side (existing, unchanged)
    spawn_x: int = 0            # Spawn chunk X
    spawn_y: int = 0            # Spawn chunk Y


@dataclass
class NationConfig:
    """Nation generation parameters."""
    count: int = 5              # Number of nations (range: 3-12)
    min_area: int = 30000       # Minimum chunks per nation
    min_corridor_width: int = 12  # Minimum corridor width in chunks
    # Deformation parameters
    deform_amplitude: float = 24.0   # Max border displacement in chunks
    deform_frequency: float = 0.02   # Noise frequency (lower = smoother)
    deform_octaves: int = 4          # Fractal noise octaves
    deform_scale_variance: float = 0.12  # Max ±12% area scaling per nation


@dataclass
class RegionConfig:
    """Region generation parameters."""
    min_per_nation: int = 3     # Minimum regions per nation
    max_per_nation: int = 8     # Maximum regions per nation
    min_area_pct: float = 0.10  # Minimum 10% of parent nation area
    max_area_pct: float = 0.45  # Maximum 45% of parent nation area
    deform_amplitude: float = 8.0
    deform_frequency: float = 0.04


@dataclass
class ProvinceConfig:
    """Province generation parameters."""
    min_area: int = 600         # Minimum chunks per province
    max_area: int = 2400        # Maximum chunks per province
    deform_amplitude: float = 4.0
    deform_frequency: float = 0.06


@dataclass
class DistrictConfig:
    """District generation parameters."""
    min_area: int = 200         # Minimum chunks per district
    max_area: int = 800         # Maximum chunks per district
    deform_amplitude: float = 2.0
    deform_frequency: float = 0.08


@dataclass
class BiomeConfig:
    """Biome generation parameters."""
    min_area: int = 400         # Minimum chunks per biome patch
    max_area: int = 800         # Maximum chunks per biome patch
    primary_weight: float = 0.70   # Probability of primary chunk types
    secondary_weight: float = 0.30  # Probability of secondary chunk types


@dataclass
class EcosystemConfig:
    """Ecosystem (danger grouping) parameters."""
    group_size: int = 3         # Chunks per side (3 = 3x3 = 9 chunks)
    gradient_max: int = 2       # Max danger level difference between neighbors
    # Danger level distribution defaults (probability weights, will be normalized)
    # These are base probabilities before biome/region modifiers
    base_danger_weights: Dict[int, float] = field(default_factory=lambda: {
        1: 0.15,   # Tranquil
        2: 0.25,   # Peaceful
        3: 0.25,   # Moderate
        4: 0.20,   # Dangerous
        5: 0.10,   # Perilous
        6: 0.05,   # Lethal
    })
    # Spawn area safety: ecosystems within this radius of (0,0) are forced Tranquil
    spawn_safe_radius: int = 2  # In ecosystem units (2 = 6x6 chunk safe zone)


@dataclass
class DungeonConfig:
    """Dungeon spawn parameters for the geographic system."""
    spawn_chance: float = 0.015   # Per-chunk chance (reduced from 0.083 for 262K world)
    min_distance_from_spawn: int = 8  # Minimum chunks from (0,0)
    excluded_in_water: bool = True


@dataclass
class GeographicConfig:
    """Master configuration for the entire geographic system."""
    world: WorldConfig = field(default_factory=WorldConfig)
    nation: NationConfig = field(default_factory=NationConfig)
    region: RegionConfig = field(default_factory=RegionConfig)
    province: ProvinceConfig = field(default_factory=ProvinceConfig)
    district: DistrictConfig = field(default_factory=DistrictConfig)
    biome: BiomeConfig = field(default_factory=BiomeConfig)
    ecosystem: EcosystemConfig = field(default_factory=EcosystemConfig)
    dungeon: DungeonConfig = field(default_factory=DungeonConfig)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> GeographicConfig:
        """Load config from JSON file, falling back to defaults.

        Args:
            config_path: Path to geography-config.json. If None, searches
                         standard locations.
        """
        cfg = cls()
        json_data = _load_json(config_path)
        if json_data:
            _apply_overrides(cfg, json_data)
        return cfg


def _load_json(config_path: Optional[str] = None) -> Optional[dict]:
    """Attempt to load geography-config.json from standard paths."""
    search_paths = []
    if config_path:
        search_paths.append(config_path)

    # Standard search locations
    base = Path(__file__).resolve().parent.parent.parent
    search_paths.extend([
        str(base / "world_system" / "config" / "geography-config.json"),
        str(base / "Definitions.JSON" / "geography-config.json"),
    ])

    for path in search_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                continue
    return None


def _apply_overrides(cfg: GeographicConfig, data: dict) -> None:
    """Apply JSON overrides to config dataclass fields."""
    section_map = {
        "world": cfg.world,
        "nation": cfg.nation,
        "region": cfg.region,
        "province": cfg.province,
        "district": cfg.district,
        "biome": cfg.biome,
        "ecosystem": cfg.ecosystem,
        "dungeon": cfg.dungeon,
    }
    for section_name, section_obj in section_map.items():
        section_data = data.get(section_name, {})
        for key, value in section_data.items():
            if hasattr(section_obj, key):
                setattr(section_obj, key, value)

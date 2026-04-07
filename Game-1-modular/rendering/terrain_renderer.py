"""Procedural terrain renderer — generates beautiful tile surfaces.

Replaces flat-color tile rendering with noise-varied, textured surfaces.
Chunk boundaries are invisible because tile colors are computed from
world-space noise, not chunk-local data.

Key principles:
- Every tile's visual is determined by (tile_type, world_x, world_y)
- World-space noise ensures seamless transitions across chunk boundaries
- Surfaces are cached after first generation for performance
- Detail layers add procedural texture (grass blades, stone cracks, etc.)
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

import pygame

from core.config import Config


# ══════════════════════════════════════════════════════════════════
# WORLD-SPACE NOISE (deterministic from position)
# ══════════════════════════════════════════════════════════════════

def _hash(x: int, y: int, seed: int = 0) -> float:
    """Fast deterministic hash → [0, 1)."""
    h = seed
    h = ((h ^ (x * 374761393)) + (y * 668265263)) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h = (h ^ (h >> 16)) & 0xFFFFFFFF
    return (h & 0x7FFFFFFF) / 0x7FFFFFFF


def _smooth_noise(x: float, y: float, seed: int = 0) -> float:
    """Smooth interpolated noise → [-1, 1]."""
    ix, iy = int(math.floor(x)), int(math.floor(y))
    fx, fy = x - ix, y - iy
    # Smoothstep
    fx = fx * fx * (3.0 - 2.0 * fx)
    fy = fy * fy * (3.0 - 2.0 * fy)
    v00 = _hash(ix, iy, seed) * 2 - 1
    v10 = _hash(ix + 1, iy, seed) * 2 - 1
    v01 = _hash(ix, iy + 1, seed) * 2 - 1
    v11 = _hash(ix + 1, iy + 1, seed) * 2 - 1
    return (v00 * (1 - fx) + v10 * fx) * (1 - fy) + (v01 * (1 - fx) + v11 * fx) * fy


def _fbm(x: float, y: float, octaves: int = 3, seed: int = 0) -> float:
    """Fractal Brownian Motion noise → approximately [-1, 1]."""
    total = 0.0
    amp = 1.0
    freq = 1.0
    max_amp = 0.0
    for i in range(octaves):
        total += _smooth_noise(x * freq, y * freq, seed + i * 7919) * amp
        max_amp += amp
        amp *= 0.5
        freq *= 2.0
    return total / max_amp


# ══════════════════════════════════════════════════════════════════
# COLOR PALETTES — rich, natural color ranges per tile type
# ══════════════════════════════════════════════════════════════════

# Each palette: (base_r, base_g, base_b, hue_variance, sat_variance, val_variance)
# Variance is max ± deviation from base
TILE_PALETTES = {
    "GRASS": {
        "base": (52, 128, 48),
        "warm": (60, 135, 46),     # Sunlit patches
        "cool": (44, 118, 50),     # Shaded areas
        "accent": (48, 140, 44),   # Lush spots
        "dark": (38, 105, 40),     # Under-canopy
        "variance": 8,             # Subtle per-pixel jitter
    },
    "STONE": {
        "base": (115, 115, 110),
        "warm": (125, 120, 108),   # Sandstone tint
        "cool": (108, 110, 118),   # Blue-grey
        "accent": (130, 128, 118), # Lighter veins
        "dark": (95, 92, 88),      # Crevices
        "variance": 6,
    },
    "WATER": {
        "base": (35, 95, 160),
        "warm": (42, 108, 168),    # Shallow / lit
        "cool": (28, 78, 145),     # Deep
        "accent": (55, 125, 185),  # Highlights
        "dark": (22, 62, 125),     # Depths
        "variance": 5,
    },
    "DIRT": {
        "base": (115, 88, 58),
        "warm": (125, 95, 62),     # Dry
        "cool": (108, 82, 55),     # Damp
        "accent": (130, 100, 68),  # Sandy patches
        "dark": (92, 72, 48),      # Rich soil
        "variance": 7,
    },
}


def _get_tile_color(tile_type_name: str, world_x: int, world_y: int) -> Tuple[int, int, int]:
    """Compute a tile's color from its type and world position.

    Uses multi-octave noise for natural variation. Two grass tiles
    next to each other (even across chunk boundaries) will have
    similar colors because the noise is world-space continuous.
    """
    palette = TILE_PALETTES.get(tile_type_name, TILE_PALETTES["GRASS"])
    base = palette["base"]

    # Large-scale terrain variation (every ~8 tiles)
    n1 = _fbm(world_x * 0.12, world_y * 0.12, octaves=2, seed=1000)

    # Medium-scale detail (every ~3 tiles)
    n2 = _fbm(world_x * 0.33, world_y * 0.33, octaves=2, seed=2000)

    # Per-tile micro-variation
    n3 = _hash(world_x, world_y, 3000) * 2 - 1

    # Blend between warm/cool based on large-scale noise
    if n1 > 0.15:
        target = palette["warm"]
        blend = min(1.0, (n1 - 0.15) * 2.5)
    elif n1 < -0.15:
        target = palette["cool"]
        blend = min(1.0, (-n1 - 0.15) * 2.5)
    else:
        target = base
        blend = 0.0

    r = base[0] + (target[0] - base[0]) * blend
    g = base[1] + (target[1] - base[1]) * blend
    b = base[2] + (target[2] - base[2]) * blend

    # Add accent spots from medium noise
    if n2 > 0.4:
        accent = palette["accent"]
        a_blend = (n2 - 0.4) * 1.5
        r = r + (accent[0] - r) * a_blend
        g = g + (accent[1] - g) * a_blend
        b = b + (accent[2] - b) * a_blend
    elif n2 < -0.4:
        dark = palette["dark"]
        d_blend = (-n2 - 0.4) * 1.5
        r = r + (dark[0] - r) * d_blend
        g = g + (dark[1] - g) * d_blend
        b = b + (dark[2] - b) * d_blend

    # Micro jitter
    v = palette["variance"]
    jitter = n3 * v
    r = max(0, min(255, int(r + jitter)))
    g = max(0, min(255, int(g + jitter * 0.8)))
    b = max(0, min(255, int(b + jitter * 0.6)))

    return (r, g, b)


# ══════════════════════════════════════════════════════════════════
# TILE SURFACE CACHE
# ══════════════════════════════════════════════════════════════════

# Cache: (world_x, world_y, tile_type) → pygame.Surface
_surface_cache: Dict[Tuple[int, int, str], pygame.Surface] = {}
_CACHE_MAX = 4096  # Max cached surfaces (fits ~64x64 viewport easily)


def get_tile_surface(tile_type_name: str, world_x: int, world_y: int,
                     tile_size: int,
                     neighbors: dict = None) -> pygame.Surface:
    """Get or generate a textured surface for a tile.

    Surfaces are cached for performance. Each tile gets a unique
    procedurally generated surface based on its world position.

    Args:
        neighbors: Optional dict of {direction: tile_type_name} for edge
                   dithering. Keys: 'n','s','e','w' for cardinal neighbors.
    """
    # Include neighbor types in cache key for edge dithering
    n_key = None
    if neighbors:
        n_key = tuple(sorted((k, v) for k, v in neighbors.items() if v != tile_type_name))
    cache_key = (world_x, world_y, tile_type_name, n_key)

    if cache_key in _surface_cache:
        return _surface_cache[cache_key]

    # Evict oldest if cache is full
    if len(_surface_cache) >= _CACHE_MAX:
        keys = list(_surface_cache.keys())
        for k in keys[:_CACHE_MAX // 4]:
            del _surface_cache[k]

    surf = pygame.Surface((tile_size, tile_size))

    # Base color from world-space noise
    base_color = _get_tile_color(tile_type_name, world_x, world_y)
    surf.fill(base_color)

    # Add procedural detail pixels for texture
    if tile_size >= 16:
        _add_tile_detail(surf, tile_type_name, world_x, world_y, tile_size)

    # Edge dithering — scatter neighbor-colored pixels at tile borders
    # Creates organic transitions instead of hard lines between tile types
    if tile_size >= 8 and neighbors:
        _add_edge_dither(surf, tile_type_name, world_x, world_y, tile_size, neighbors)

    _surface_cache[cache_key] = surf
    return surf


def _add_tile_detail(surf: pygame.Surface, tile_type: str,
                     wx: int, wy: int, size: int) -> None:
    """Add procedural detail to a tile surface for visual richness."""

    if tile_type == "GRASS":
        # Scatter grass blade dots and small highlights
        for i in range(size // 4):
            px = int(_hash(wx * 100 + i, wy, 5000) * size)
            py = int(_hash(wx, wy * 100 + i, 5001) * size)
            brightness = _hash(wx + i, wy + i, 5002)
            if brightness > 0.6:
                # Light grass blade
                c = (60, 155, 50)
                surf.set_at((min(px, size - 1), min(py, size - 1)), c)
                if py + 1 < size:
                    surf.set_at((min(px, size - 1), py + 1), c)
            elif brightness < 0.2:
                # Dark spot
                c = (28, 85, 30)
                surf.set_at((min(px, size - 1), min(py, size - 1)), c)

    elif tile_type == "STONE":
        # Subtle crack lines and mineral specks
        for i in range(size // 6):
            px = int(_hash(wx * 100 + i, wy, 6000) * size)
            py = int(_hash(wx, wy * 100 + i, 6001) * size)
            val = _hash(wx + i * 3, wy + i * 7, 6002)
            if val > 0.75:
                # Light mineral speck
                surf.set_at((min(px, size - 1), min(py, size - 1)), (155, 150, 140))
            elif val < 0.15:
                # Dark crack pixel
                surf.set_at((min(px, size - 1), min(py, size - 1)), (70, 68, 65))
                # Extend crack slightly
                if px + 1 < size:
                    surf.set_at((px + 1, min(py, size - 1)), (75, 72, 68))

    elif tile_type == "WATER":
        # Subtle wave highlights
        for i in range(size // 5):
            px = int(_hash(wx * 100 + i, wy, 7000) * size)
            py = int(_hash(wx, wy * 100 + i, 7001) * size)
            if _hash(wx + i, wy + i, 7002) > 0.7:
                c = (75, 155, 210)
                surf.set_at((min(px, size - 1), min(py, size - 1)), c)
                if px + 1 < size:
                    surf.set_at((px + 1, min(py, size - 1)), c)

    elif tile_type == "DIRT":
        # Pebbles and soil texture
        for i in range(size // 5):
            px = int(_hash(wx * 100 + i, wy, 8000) * size)
            py = int(_hash(wx, wy * 100 + i, 8001) * size)
            val = _hash(wx + i * 5, wy + i * 3, 8002)
            if val > 0.8:
                # Small pebble (light)
                surf.set_at((min(px, size - 1), min(py, size - 1)), (155, 130, 95))
            elif val < 0.1:
                # Dark soil
                surf.set_at((min(px, size - 1), min(py, size - 1)), (72, 50, 32))


def _add_edge_dither(surf: pygame.Surface, tile_type: str,
                     wx: int, wy: int, size: int,
                     neighbors: dict) -> None:
    """Scatter neighbor-colored pixels at tile edges for organic transitions.

    Instead of hard lines between grass and stone, dithers the boundary
    with scattered pixels that fade in density toward the center.
    """
    dither_depth = max(2, size // 4)  # How far dithering reaches into tile

    for direction, n_type in neighbors.items():
        if n_type == tile_type:
            continue

        n_palette = TILE_PALETTES.get(n_type, TILE_PALETTES["GRASS"])
        n_color = n_palette["base"]
        # Darken slightly for a natural shadow at transitions
        shadow = (max(0, n_color[0] - 10), max(0, n_color[1] - 10), max(0, n_color[2] - 10))

        for i in range(size * dither_depth // 3):
            # Hash-based deterministic pixel placement
            h = _hash(wx * 200 + i, wy * 200 + ord(direction[0]), 4444)
            h2 = _hash(wx + i * 7, wy + i * 3, 4445)

            if direction == 'n':
                px = int(h * size)
                py = int(h2 * dither_depth)
                density = 1.0 - (py / dither_depth)  # Denser near edge
            elif direction == 's':
                px = int(h * size)
                py = size - 1 - int(h2 * dither_depth)
                density = 1.0 - ((size - 1 - py) / dither_depth)
            elif direction == 'w':
                px = int(h2 * dither_depth)
                py = int(h * size)
                density = 1.0 - (px / dither_depth)
            elif direction == 'e':
                px = size - 1 - int(h2 * dither_depth)
                py = int(h * size)
                density = 1.0 - ((size - 1 - px) / dither_depth)
            else:
                continue

            # Probabilistic placement — denser near edge, sparser toward center
            if _hash(wx + i, wy + i * 11, 4446) < density * 0.6:
                px = max(0, min(size - 1, px))
                py = max(0, min(size - 1, py))
                # Blend with existing pixel for softer look
                existing = surf.get_at((px, py))
                blended = (
                    (existing[0] + shadow[0]) // 2,
                    (existing[1] + shadow[1]) // 2,
                    (existing[2] + shadow[2]) // 2,
                )
                surf.set_at((px, py), blended)


def _get_tile_color_with_offset(tile_type_name, wx, wy, seed_offset=0):
    """Variant of _get_tile_color for neighbor color lookup."""
    palette = TILE_PALETTES.get(tile_type_name, TILE_PALETTES["GRASS"])
    return palette["base"]


def clear_terrain_cache() -> None:
    """Clear the terrain surface cache (call on resolution change)."""
    _surface_cache.clear()

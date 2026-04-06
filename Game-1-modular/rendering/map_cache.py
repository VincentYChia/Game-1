"""Pre-rendered map image cache for the geographic world map.

Generates smooth, high-quality map images at startup. The map renderer
blits viewport regions from these cached surfaces — zero per-chunk
iteration at render time.

Key quality features:
- Smooth color blending (box blur) eliminates per-chunk speckle
- Thick nation borders that scale well at any zoom
- Region borders at higher LOD
- Stronger nation color tinting for clear political distinction
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import pygame


def _box_blur(surf: pygame.Surface, radius: int = 1) -> pygame.Surface:
    """Fast box blur using pygame scale-down then scale-up.

    This is the standard pygame blur trick: scale to 1/N, then back up.
    The interpolation during scale-up creates a natural blur effect.
    """
    if radius <= 0:
        return surf
    w, h = surf.get_size()
    # Scale down by factor, then back up — the interpolation creates blur
    factor = max(1, radius + 1)
    small_w = max(1, w // factor)
    small_h = max(1, h // factor)
    small = pygame.transform.smoothscale(surf, (small_w, small_h))
    return pygame.transform.smoothscale(small, (w, h))


def generate_map_images(
    world_map,
    biome_color_fn,
    nation_colors: Dict[int, Tuple[int, int, int]],
) -> Dict[int, pygame.Surface]:
    """Generate pre-rendered map images.

    Produces a single high-quality image at 4px/chunk (2048x2048 for 512 world),
    with smooth blurred colors and clear borders.
    """
    world_size = world_map.world_size
    half = world_size // 2
    chunk_data = world_map.chunk_data

    ppc = 4  # pixels per chunk
    img_size = world_size * ppc
    surf = pygame.Surface((img_size, img_size))
    surf.fill((20, 22, 30))

    # Pass 1: Draw chunk colors with stronger nation tinting
    for (cx, cy), geo in chunk_data.items():
        ct_value = geo.chunk_type.value if hasattr(geo.chunk_type, 'value') else str(geo.chunk_type)
        color = biome_color_fn(ct_value)

        # Stronger nation tint (25%) for clear political distinction
        nc = nation_colors.get(geo.nation_id)
        if nc:
            color = (
                int(color[0] * 0.75 + nc[0] * 0.25),
                int(color[1] * 0.75 + nc[1] * 0.25),
                int(color[2] * 0.75 + nc[2] * 0.25),
            )

        px = (cx + half) * ppc
        py = (cy + half) * ppc
        pygame.draw.rect(surf, color, (px, py, ppc, ppc))

    # Pass 2: Stronger blur to eliminate checkerboard noise → smooth painted look
    surf = _box_blur(surf, radius=3)

    # Pass 3: Draw nation borders (thick, on top of blur so they stay crisp)
    border_color = (200, 185, 140)
    for (cx, cy), geo in chunk_data.items():
        right = chunk_data.get((cx + 1, cy))
        if right and geo.nation_id != right.nation_id:
            x = (cx + half + 1) * ppc
            y = (cy + half) * ppc
            pygame.draw.line(surf, border_color, (x - 1, y), (x - 1, y + ppc), 2)

        bottom = chunk_data.get((cx, cy + 1))
        if bottom and geo.nation_id != bottom.nation_id:
            x = (cx + half) * ppc
            y = (cy + half + 1) * ppc
            pygame.draw.line(surf, border_color, (x, y - 1), (x + ppc, y - 1), 2)

    # Pass 4: Region borders (thinner)
    region_color = (140, 140, 155, 180)
    for (cx, cy), geo in chunk_data.items():
        right = chunk_data.get((cx + 1, cy))
        if right and geo.nation_id == right.nation_id and geo.region_id != right.region_id:
            x = (cx + half + 1) * ppc
            y = (cy + half) * ppc
            pygame.draw.line(surf, (120, 120, 135), (x, y), (x, y + ppc), 1)

        bottom = chunk_data.get((cx, cy + 1))
        if bottom and geo.nation_id == bottom.nation_id and geo.region_id != bottom.region_id:
            x = (cx + half) * ppc
            y = (cy + half + 1) * ppc
            pygame.draw.line(surf, (120, 120, 135), (x, y), (x + ppc, y), 1)

    results = {ppc: surf}

    # Also generate a small overview (1px/chunk, blurred) for extreme zoom-out
    small = pygame.transform.smoothscale(surf, (world_size, world_size))
    results[1] = small

    print(f"[MapCache] Generated map image: {img_size}x{img_size} (blurred, bordered)")
    return results


def get_best_lod(
    map_images: Dict[int, pygame.Surface],
    chunk_size_pixels: float,
) -> Optional[Tuple[pygame.Surface, int]]:
    """Select the best LOD surface for the current zoom level."""
    if not map_images:
        return None
    # Always use highest quality
    best_ppc = max(map_images.keys())
    return (map_images[best_ppc], best_ppc)

"""Pre-rendered map image cache for the geographic world map.

Generates static map images at multiple LOD (level of detail) tiers
after world generation. The map renderer blits from these cached
surfaces instead of iterating 262K chunks per frame.

LOD tiers:
- Tier 0: 512x512 (1px/chunk) — full world overview
- Tier 1: 1024x1024 (2px/chunk) — medium zoom
- Tier 2: 2048x2048 (4px/chunk) — closer zoom

At close zoom (>8px/chunk), falls back to per-chunk rendering
since only a few hundred chunks are visible.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import pygame


def generate_map_images(
    world_map,
    biome_color_fn,
    nation_colors: Dict[int, Tuple[int, int, int]],
) -> Dict[int, pygame.Surface]:
    """Generate pre-rendered map images at multiple LOD levels.

    Args:
        world_map: WorldMap from geographic system.
        biome_color_fn: Function(chunk_type_str) → (r, g, b).
        nation_colors: Dict mapping nation_id → (r, g, b).

    Returns:
        Dict mapping pixels_per_chunk → pygame.Surface.
    """
    world_size = world_map.world_size
    half = world_size // 2
    chunk_data = world_map.chunk_data

    results = {}

    for ppc in [1, 2, 4]:
        img_size = world_size * ppc
        surf = pygame.Surface((img_size, img_size))
        surf.fill((15, 15, 25))

        for (cx, cy), geo in chunk_data.items():
            # Chunk type color
            ct_value = geo.chunk_type.value if hasattr(geo.chunk_type, 'value') else str(geo.chunk_type)
            color = biome_color_fn(ct_value)

            # Nation tint
            nc = nation_colors.get(geo.nation_id)
            if nc:
                color = (
                    int(color[0] * 0.85 + nc[0] * 0.15),
                    int(color[1] * 0.85 + nc[1] * 0.15),
                    int(color[2] * 0.85 + nc[2] * 0.15),
                )

            # Convert chunk coords to pixel coords
            px = (cx + half) * ppc
            py = (cy + half) * ppc

            if ppc == 1:
                surf.set_at((px, py), color)
            else:
                pygame.draw.rect(surf, color, (px, py, ppc, ppc))

        # Draw nation borders on higher LOD tiers
        if ppc >= 2:
            border_color = (220, 200, 160)
            for (cx, cy), geo in chunk_data.items():
                # Check right neighbor
                right = chunk_data.get((cx + 1, cy))
                if right and geo.nation_id != right.nation_id:
                    x = (cx + half + 1) * ppc
                    y = (cy + half) * ppc
                    pygame.draw.line(surf, border_color, (x, y), (x, y + ppc), 1)
                # Check bottom neighbor
                bottom = chunk_data.get((cx, cy + 1))
                if bottom and geo.nation_id != bottom.nation_id:
                    x = (cx + half) * ppc
                    y = (cy + half + 1) * ppc
                    pygame.draw.line(surf, border_color, (x, y), (x + ppc, y), 1)

            # Region borders (thinner, only on highest pre-rendered tier)
            if ppc >= 4:
                region_color = (160, 160, 180)
                for (cx, cy), geo in chunk_data.items():
                    right = chunk_data.get((cx + 1, cy))
                    if right and geo.nation_id == right.nation_id and geo.region_id != right.region_id:
                        x = (cx + half + 1) * ppc
                        y = (cy + half) * ppc
                        pygame.draw.line(surf, region_color, (x, y), (x, y + ppc), 1)
                    bottom = chunk_data.get((cx, cy + 1))
                    if bottom and geo.nation_id == bottom.nation_id and geo.region_id != bottom.region_id:
                        x = (cx + half) * ppc
                        y = (cy + half + 1) * ppc
                        pygame.draw.line(surf, region_color, (x, y), (x + ppc, y), 1)

        results[ppc] = surf
        print(f"[MapCache] Generated LOD tier {ppc}px/chunk: {img_size}x{img_size}")

    return results


def get_best_lod(
    map_images: Dict[int, pygame.Surface],
    chunk_size_pixels: float,
) -> Optional[Tuple[pygame.Surface, int]]:
    """Select the best LOD surface for the current zoom level.

    Returns (surface, pixels_per_chunk) or None if zoom is too close
    for pre-rendered images (fall back to per-chunk rendering).
    """
    # At 8+ px/chunk, per-chunk rendering is fine (few chunks visible)
    if chunk_size_pixels > 8:
        return None

    # Pick the LOD tier closest to (but not exceeding) current chunk size
    best_ppc = None
    best_surf = None
    for ppc in sorted(map_images.keys(), reverse=True):
        if ppc <= chunk_size_pixels or best_ppc is None:
            best_ppc = ppc
            best_surf = map_images[ppc]
            break

    # Fallback to lowest LOD
    if best_surf is None and map_images:
        best_ppc = min(map_images.keys())
        best_surf = map_images[best_ppc]

    return (best_surf, best_ppc) if best_surf else None

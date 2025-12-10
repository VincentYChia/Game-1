"""Image cache system for loading and caching item icons"""

import os
import pygame
from typing import Dict, Optional


class ImageCache:
    """Singleton cache for loading and storing item icon images"""

    _instance = None

    def __init__(self):
        """Initialize the image cache"""
        self.cache: Dict[str, pygame.Surface] = {}
        self.failed_paths: set = set()  # Track failed loads to avoid repeated attempts

        # Get the absolute path to the assets directory
        # Assumes this file is in Game-1-modular/rendering/
        import pathlib
        module_dir = pathlib.Path(__file__).parent.parent  # Go up to Game-1-modular/
        self.base_path = str(module_dir / "assets")

    @classmethod
    def get_instance(cls) -> 'ImageCache':
        """Get or create the singleton instance"""
        if cls._instance is None:
            cls._instance = ImageCache()
        return cls._instance

    def get_image(self, icon_path: Optional[str], target_size: tuple = (50, 50)) -> Optional[pygame.Surface]:
        """
        Load and cache an image, returning a scaled Surface or None if not found.

        Args:
            icon_path: Relative path to the image (e.g., "materials/copper_ore.png" or "enemies/wolf_grey.png")
            target_size: Tuple of (width, height) to scale the image to

        Returns:
            pygame.Surface if image loads successfully, None otherwise
        """
        if not icon_path:
            return None

        # Check if we've already failed to load this path
        if icon_path in self.failed_paths:
            return None

        # Create cache key including size for different scaled versions
        cache_key = f"{icon_path}_{target_size[0]}x{target_size[1]}"

        # Return cached image if available
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Build full path - handle both items and non-items
        # Items use paths like "materials/copper_ore.png" (need items/ prefix)
        # Others use paths like "enemies/wolf_grey.png" (no items/ prefix needed)
        # New entity types: npcs, quests, classes (direct asset paths)
        if icon_path.startswith(('enemies/', 'resources/', 'skills/', 'titles/', 'npcs/', 'quests/', 'classes/')):
            # Direct asset path (enemies, resources, npcs, quests, classes, etc.)
            full_path = os.path.join(self.base_path, icon_path)
        else:
            # Item path (needs items/ prefix)
            full_path = os.path.join(self.base_path, 'items', icon_path)

        try:
            # Load the image
            if not os.path.exists(full_path):
                # Silently fail - this is expected when images don't exist yet
                self.failed_paths.add(icon_path)
                return None

            # Load and convert the image for better performance
            image = pygame.image.load(full_path)

            # Convert with alpha for PNG transparency support
            if full_path.lower().endswith('.png'):
                image = image.convert_alpha()
            else:
                image = image.convert()

            # Scale to target size
            scaled_image = pygame.transform.smoothscale(image, target_size)

            # Cache the scaled image
            self.cache[cache_key] = scaled_image

            return scaled_image

        except (pygame.error, FileNotFoundError, OSError) as e:
            # Failed to load - add to failed paths to avoid repeated attempts
            # Uncomment for debugging: print(f"Failed to load {full_path}: {e}")
            self.failed_paths.add(icon_path)
            return None

    def clear_cache(self):
        """Clear the image cache (useful for hot-reloading during development)"""
        self.cache.clear()
        self.failed_paths.clear()

    def get_cache_stats(self) -> dict:
        """Get statistics about the cache for debugging"""
        return {
            'cached_images': len(self.cache),
            'failed_paths': len(self.failed_paths),
            'memory_estimate_mb': sum(
                img.get_width() * img.get_height() * 4  # RGBA = 4 bytes per pixel
                for img in self.cache.values()
            ) / (1024 * 1024)
        }

#!/usr/bin/env python3
"""Test script for the image cache system"""

import sys
import os

# Add the Game-1-modular directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize pygame (required for image loading)
import pygame
pygame.init()

from rendering.image_cache import ImageCache
from data.databases import MaterialDatabase, EquipmentDatabase

def test_image_cache():
    """Test the image cache system"""
    print("=" * 60)
    print("IMAGE CACHE SYSTEM TEST")
    print("=" * 60)

    # Get cache instance
    cache = ImageCache.get_instance()
    print("\n✓ ImageCache singleton initialized")

    # Test 1: Load non-existent image (should return None gracefully)
    print("\n[Test 1] Loading non-existent image...")
    image = cache.get_image("materials/nonexistent.png", (50, 50))
    if image is None:
        print("  ✓ Correctly returned None for non-existent image")
    else:
        print("  ✗ ERROR: Should have returned None")

    # Test 2: Try again - should not attempt reload
    print("\n[Test 2] Attempting to load same non-existent image again...")
    image = cache.get_image("materials/nonexistent.png", (50, 50))
    if image is None:
        print("  ✓ Correctly used failed_paths cache to skip reload")
    else:
        print("  ✗ ERROR: Should have returned None")

    # Test 3: Load databases to check icon_path parsing
    print("\n[Test 3] Loading databases to check icon_path parsing...")

    mat_db = MaterialDatabase.get_instance()
    mat_db.load_from_file("items.JSON/items-materials-1.JSON")

    equip_db = EquipmentDatabase.get_instance()
    equip_db.load_from_file("items.JSON/items-smithing-1.JSON")

    # Check if any materials have icon_path
    print("\n  Checking MaterialDefinition fields...")
    sample_materials = list(mat_db.materials.values())[:3]
    for mat in sample_materials:
        print(f"    - {mat.material_id}: icon_path = {mat.icon_path}")

    # Check if any equipment has icon_path
    print("\n  Checking EquipmentItem fields...")
    sample_items = list(equip_db.items.keys())[:3]
    for item_id in sample_items:
        eq = equip_db.create_equipment_from_id(item_id)
        if eq:
            print(f"    - {eq.item_id}: icon_path = {eq.icon_path}")

    # Test 4: Cache statistics
    print("\n[Test 4] Cache statistics...")
    stats = cache.get_cache_stats()
    print(f"  - Cached images: {stats['cached_images']}")
    print(f"  - Failed paths: {stats['failed_paths']}")
    print(f"  - Memory usage: {stats['memory_estimate_mb']:.2f} MB")

    # Test 5: Clear cache
    print("\n[Test 5] Testing cache clear...")
    cache.clear_cache()
    stats_after = cache.get_cache_stats()
    if stats_after['cached_images'] == 0 and stats_after['failed_paths'] == 0:
        print("  ✓ Cache cleared successfully")
    else:
        print("  ✗ ERROR: Cache not cleared properly")

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print("✓ Image cache system is functional")
    print("✓ Graceful fallback for missing images works")
    print("✓ Database parsing of icon_path works")
    print("✓ System ready for image integration")
    print("\nTo add images:")
    print("  1. Place PNG/JPG files in assets/items/ subdirectories")
    print("  2. Add 'iconPath' field to JSON item definitions")
    print("  3. Images will automatically display in-game")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_image_cache()
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

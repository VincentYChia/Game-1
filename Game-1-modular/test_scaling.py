#!/usr/bin/env python3
"""Test script to verify UI scaling is working"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
from core.config import Config

def test_scaling():
    print("=" * 60)
    print("UI SCALING DIAGNOSTIC TEST")
    print("=" * 60)

    # Initialize
    Config.init_screen_settings()

    print(f"\n✅ Screen initialized successfully")
    print(f"   Resolution: {Config.SCREEN_WIDTH}x{Config.SCREEN_HEIGHT}")
    print(f"   Fullscreen: {Config.FULLSCREEN}")
    print(f"   UI Scale Factor: {Config.UI_SCALE:.3f}x")

    print(f"\n📏 Scaling Test:")
    test_values = [10, 50, 100, 500, 1000]
    for val in test_values:
        scaled = Config.scale(val)
        print(f"   scale({val:4d}) = {scaled:4d}  (diff: {scaled-val:+4d})")

    print(f"\n📐 Preset Menu Sizes:")
    print(f"   MENU_SMALL:   {Config.MENU_SMALL_W}x{Config.MENU_SMALL_H}   (base: 600x500)")
    print(f"   MENU_MEDIUM:  {Config.MENU_MEDIUM_W}x{Config.MENU_MEDIUM_H}  (base: 800x600)")
    print(f"   MENU_LARGE:   {Config.MENU_LARGE_W}x{Config.MENU_LARGE_H}   (base: 1000x700)")
    print(f"   MENU_XLARGE:  {Config.MENU_XLARGE_W}x{Config.MENU_XLARGE_H}  (base: 1200x750)")

    print(f"\n🎮 Viewport:")
    print(f"   Size: {Config.VIEWPORT_WIDTH}x{Config.VIEWPORT_HEIGHT}")
    print(f"   UI Panel: {Config.UI_PANEL_WIDTH}px")

    print(f"\n📦 Inventory:")
    print(f"   Panel Y: {Config.INVENTORY_PANEL_Y}")
    print(f"   Slot Size: {Config.INVENTORY_SLOT_SIZE}px (base: 50px)")
    print(f"   Slots Per Row: {Config.INVENTORY_SLOTS_PER_ROW}")

    # Test font scaling
    screen = pygame.display.set_mode((Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT))
    font_normal = pygame.font.Font(None, Config.scale(24))
    font_small = pygame.font.Font(None, Config.scale(18))
    font_tiny = pygame.font.Font(None, Config.scale(14))

    print(f"\n🔤 Font Sizes:")
    print(f"   Normal: {Config.scale(24)}px (base: 24px)")
    print(f"   Small:  {Config.scale(18)}px (base: 18px)")
    print(f"   Tiny:   {Config.scale(14)}px (base: 14px)")

    print(f"\n" + "=" * 60)
    if abs(Config.UI_SCALE - 1.0) < 0.01:
        print("⚠️  WARNING: UI_SCALE is ~1.0")
        print("   This means your screen is close to the base 900px height.")
        print("   You won't see much visual difference in UI scaling.")
        print("   Try pressing F11 for fullscreen or test on a different resolution.")
    else:
        print(f"✅ UI_SCALE is {Config.UI_SCALE:.3f}x - scaling should be visible!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_scaling()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

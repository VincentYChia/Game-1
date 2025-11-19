#!/usr/bin/env python3
"""
Verify all imports in the modular Game-1 codebase.
Run this to check if the module structure is correct.
"""

import sys
import os

# Add current directory to path (same as main.py does)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Verifying all imports...")
print("=" * 60)

errors = []
warnings = []

# Test core modules
print("\n[Core Modules]")
try:
    from core import Config
    print("✓ core.Config")
except Exception as e:
    errors.append(f"core.Config: {e}")
    print(f"❌ core.Config: {e}")

try:
    from core import Camera
    print("✓ core.Camera")
except Exception as e:
    errors.append(f"core.Camera: {e}")
    print(f"❌ core.Camera: {e}")

try:
    from core import Notification
    print("✓ core.Notification")
except Exception as e:
    errors.append(f"core.Notification: {e}")
    print(f"❌ core.Notification: {e}")

# Test data models
print("\n[Data Models]")
try:
    from data.models import Position, Recipe, EquipmentItem, MaterialDefinition
    print("✓ data.models (Position, Recipe, EquipmentItem, MaterialDefinition)")
except Exception as e:
    errors.append(f"data.models: {e}")
    print(f"❌ data.models: {e}")

# Test data databases
print("\n[Data Databases]")
try:
    from data.databases import MaterialDatabase, EquipmentDatabase, SkillDatabase
    print("✓ data.databases (MaterialDatabase, EquipmentDatabase, SkillDatabase)")
except Exception as e:
    errors.append(f"data.databases: {e}")
    print(f"❌ data.databases: {e}")

# Test entities
print("\n[Entities]")
try:
    from entities import Character, Tool, DamageNumber
    print("✓ entities (Character, Tool, DamageNumber)")
except Exception as e:
    errors.append(f"entities: {e}")
    print(f"❌ entities: {e}")

try:
    from entities.components import Inventory, SkillManager, EquipmentManager
    print("✓ entities.components (Inventory, SkillManager, EquipmentManager)")
except Exception as e:
    errors.append(f"entities.components: {e}")
    print(f"❌ entities.components: {e}")

# Test systems
print("\n[Systems]")
try:
    from systems import WorldSystem, QuestManager, TitleSystem
    print("✓ systems (WorldSystem, QuestManager, TitleSystem)")
except Exception as e:
    errors.append(f"systems: {e}")
    print(f"❌ systems: {e}")

# Test rendering (might fail if pygame not installed)
print("\n[Rendering]")
try:
    from rendering import Renderer
    print("✓ rendering.Renderer")
except ImportError as e:
    if 'pygame' in str(e):
        warnings.append("rendering.Renderer requires pygame (not installed in test environment)")
        print("⚠ rendering.Renderer - pygame not installed (expected in test environment)")
    else:
        errors.append(f"rendering.Renderer: {e}")
        print(f"❌ rendering.Renderer: {e}")
except Exception as e:
    errors.append(f"rendering.Renderer: {e}")
    print(f"❌ rendering.Renderer: {e}")

# Test game engine
print("\n[Game Engine]")
try:
    from core.game_engine import GameEngine
    print("✓ core.game_engine.GameEngine")
except ImportError as e:
    if 'pygame' in str(e):
        warnings.append("GameEngine requires pygame (not installed in test environment)")
        print("⚠ core.game_engine.GameEngine - pygame not installed (expected in test environment)")
    else:
        errors.append(f"GameEngine: {e}")
        print(f"❌ GameEngine: {e}")
except Exception as e:
    errors.append(f"GameEngine: {e}")
    print(f"❌ GameEngine: {e}")

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

if errors:
    print(f"\n❌ {len(errors)} CRITICAL ERRORS:")
    for error in errors:
        print(f"  - {error}")
    sys.exit(1)
else:
    print("\n✓ All critical imports successful!")

if warnings:
    print(f"\n⚠ {len(warnings)} warnings (expected):")
    for warning in warnings:
        print(f"  - {warning}")

print("\n✓ Module structure is correct!")
print("  All imports work when sys.path is set up correctly.")
print("  Make sure to run the game via main.py, not individual files.")

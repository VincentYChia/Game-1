"""Faction System - NPC belonging, affinity, and reputation tracking.

Core components:
- TagRegistry: Durable dictionary of all tags used in game
- AffinityDefaults: Hierarchical affinity defaults (world → nation → locality)
- FactionSystem: Main system (player rep, faction relationships, ripple effects)

Usage:
    from world_system.living_world.factions import initialize_faction_systems
    initialize_faction_systems()

    registry = TagRegistry.get_instance()
    affinity = AffinityDefaults.get_instance()
    faction = FactionSystem.get_instance()
"""

from .tag_registry import TagRegistry
from .affinity_defaults import AffinityDefaults
from .faction_system import FactionSystem
from typing import Dict, Any


def initialize_faction_systems() -> None:
    """Initialize all faction system components.

    Called from game_engine._init_world_memory().
    Ensures TagRegistry and AffinityDefaults are loaded before any faction logic.
    """
    try:
        # Load registries first (no dependencies)
        TagRegistry.get_instance()
        AffinityDefaults.get_instance()
        print("✓ Faction systems initialized (TagRegistry, AffinityDefaults)")
    except Exception as e:
        print(f"⚠ Faction system init failed (non-fatal): {e}")


def save_faction_systems() -> Dict[str, Any]:
    """Serialize all faction system state for saving.

    Returns:
        Dictionary containing faction state (for save_manager.create_save_data)
    """
    save_data = {
        "tag_registry": {},  # Registry is persisted automatically
        "affinity_defaults": {}  # Affinity defaults are persisted automatically
    }

    # FactionSystem state (if using old system)
    try:
        faction = FactionSystem.get_instance()
        # FactionSystem has its own save mechanism (see faction_system.py)
    except Exception as e:
        print(f"⚠ Error saving faction state: {e}")

    return save_data


def restore_faction_systems(save_data: Dict[str, Any]) -> None:
    """Restore faction system state from save data.

    Args:
        save_data: Dictionary from save file
    """
    try:
        # Registries load from disk automatically
        # FactionSystem restoration handled internally
        pass
    except Exception as e:
        print(f"⚠ Error restoring faction state: {e}")

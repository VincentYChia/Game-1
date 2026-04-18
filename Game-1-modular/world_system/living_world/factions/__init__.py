"""Faction System — Parallel recording layer to WMS.

Core components:
- FactionSystem: SQLite-backed NPC + player affinity tracking
- ReputationRulesEngine: Maps events to affinity deltas
- WMS Evaluator: Consolidates affinity changes into narratives

Usage:
    from world_system.living_world.factions import initialize_faction_systems
    initialize_faction_systems()

    from world_system.living_world.factions import FactionSystem
    faction_sys = FactionSystem.get_instance()
"""

from .faction_system import FactionSystem
from typing import Dict, Any


def initialize_faction_systems() -> None:
    """Initialize faction system at game startup.

    Called from game_engine._init_world_memory().
    Sets up SQLite, creates tables, and bootstraps location affinity defaults.
    """
    try:
        # Initialize FactionSystem database
        faction_sys = FactionSystem.get_instance()
        faction_sys.initialize()
        print("✓ Faction system initialized")

    except Exception as e:
        print(f"✗ Faction system initialization failed: {e}")
        raise


def save_faction_systems() -> Dict[str, Any]:
    """Save faction state (database persists independently)."""
    try:
        faction_sys = FactionSystem.get_instance()
        return faction_sys.save()
    except Exception as e:
        print(f"⚠ Error saving faction state: {e}")
        return {}


def restore_faction_systems(data: Dict[str, Any]) -> None:
    """Restore faction state."""
    try:
        faction_sys = FactionSystem.get_instance()
        faction_sys.load(data)
    except Exception as e:
        print(f"⚠ Error restoring faction state: {e}")

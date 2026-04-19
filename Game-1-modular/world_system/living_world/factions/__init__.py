"""Faction System — parallel recording layer to WMS.

Core components:
- FactionSystem: SQLite-backed NPC + player affinity tracking
- WMS FactionReputationEvaluator (in world_memory/evaluators): consolidates
  FACTION_AFFINITY_CHANGED events into Layer 2 narratives.

Usage:
    from world_system.living_world.factions import initialize_faction_systems
    initialize_faction_systems()

    from world_system.living_world.factions import FactionSystem
    faction_sys = FactionSystem.get_instance()
"""

from typing import Any, Dict

from .faction_system import FactionSystem, FACTION_AFFINITY_CHANGED
from .consolidator import AffinityConsolidator, FACTION_AFFINITY_CONSOLIDATED
from .quest_tool import QuestGenerator

__all__ = [
    "FactionSystem",
    "FACTION_AFFINITY_CHANGED",
    "AffinityConsolidator",
    "FACTION_AFFINITY_CONSOLIDATED",
    "QuestGenerator",
    "initialize_faction_systems",
    "save_faction_systems",
    "restore_faction_systems",
]


def initialize_faction_systems() -> None:
    """Initialize faction system at game startup.

    Called from game_engine._init_world_memory(). Creates SQLite tables and
    bootstraps location affinity defaults.
    """
    try:
        faction_sys = FactionSystem.get_instance()
        faction_sys.initialize()
        print("[Factions] System initialized")
    except Exception as e:
        print(f"[Factions] Initialization failed: {e}")
        raise


def save_faction_systems() -> Dict[str, Any]:
    """Save faction state (SQLite file persists independently)."""
    try:
        return FactionSystem.get_instance().save()
    except Exception as e:
        print(f"[Factions] Error saving state: {e}")
        return {}


def restore_faction_systems(data: Dict[str, Any]) -> None:
    """Restore faction state."""
    try:
        FactionSystem.get_instance().load(data)
    except Exception as e:
        print(f"[Factions] Error restoring state: {e}")

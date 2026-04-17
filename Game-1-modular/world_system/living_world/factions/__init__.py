"""Faction System - NPC belonging, affinity, and reputation tracking.

Phase 2 Implementation: NPC Faction Profiles & Player Affinity

Core components:
- FactionDatabase: Singleton SQLite database for NPC profiles, player affinity, quest logs
- Models: NPCFactionProfile, PlayerAffinityProfile, NPCBelongingTag, etc.
- Schema: Table definitions (affinity_defaults, npc_profiles, npc_belonging, player_affinity, quest_log)

Usage:
    from world_system.living_world.factions import initialize_faction_systems, save_faction_systems, restore_faction_systems

    # Initialize at startup
    initialize_faction_systems()

    # Access database
    from world_system.living_world.factions.database import FactionDatabase
    db = FactionDatabase.get_instance()
    npc = db.get_npc_profile("npc_1")

    # Save/restore
    faction_state = save_faction_systems()
    restore_faction_systems(faction_state)
"""

from .database import FactionDatabase
from typing import Dict, Any


def initialize_faction_systems() -> None:
    """Initialize FactionDatabase and create schema.

    Called from game_engine._init_world_memory() before WMS.
    Sets up SQLite connection, creates tables, and seeds bootstrap affinity defaults.
    """
    try:
        db = FactionDatabase.get_instance()
        db.initialize()
        print("✓ Faction database initialized")
    except Exception as e:
        print(f"✗ Faction system initialization failed: {e}")
        raise


def save_faction_systems() -> Dict[str, Any]:
    """Prepare faction state for save file.

    Returns:
        Empty dict (faction data persists in SQLite, not in save file)
    """
    try:
        db = FactionDatabase.get_instance()
        # FactionDatabase persists automatically to faction.db in save directory
        # No additional save needed beyond database commits
        return {}
    except Exception as e:
        print(f"⚠ Error saving faction state: {e}")
        return {}


def restore_faction_systems(save_data: Dict[str, Any]) -> None:
    """Restore faction database from save.

    Args:
        save_data: Dictionary from save file (unused, faction data in SQLite)
    """
    try:
        # Database connection persists across load cycles
        # No restoration needed—faction.db is already open
        pass
    except Exception as e:
        print(f"⚠ Error restoring faction state: {e}")

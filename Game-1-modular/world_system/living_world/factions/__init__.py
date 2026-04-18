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
from .quest_listener import FactionQuestListener
from .faction_dialogue_generator import FactionDialogueGenerator
from .affinity_features import (
    AffinityTierSystem,
    AffinityRippleSystem,
    AffinityDecayScheduler,
    AffinityMilestoneSystem,
)
from typing import Dict, Any, Optional


# Global instances for Phase 4-6 systems
_dialogue_generator: Optional[FactionDialogueGenerator] = None
_tier_system: Optional[AffinityTierSystem] = None
_ripple_system: Optional[AffinityRippleSystem] = None
_decay_scheduler: Optional[AffinityDecayScheduler] = None
_milestone_system: Optional[AffinityMilestoneSystem] = None


def initialize_faction_systems(enable_decay: bool = True,
                              enable_milestones: bool = True) -> None:
    """Initialize all faction systems (Phases 2-6).

    Called from game_engine._init_world_memory() before WMS.
    Sets up SQLite, quest listener, and advanced affinity features.

    Args:
        enable_decay: Start background affinity decay scheduler (Phase 6).
        enable_milestones: Enable milestone tracking (Phase 6).
    """
    global _dialogue_generator, _tier_system, _ripple_system, _decay_scheduler, _milestone_system

    try:
        # Phase 2: Database initialization
        db = FactionDatabase.get_instance()
        db.initialize()
        print("✓ Faction database initialized (Phase 2)")

        # Phase 3: Quest event listener
        listener = FactionQuestListener.get_instance()
        listener.initialize()
        print("✓ Faction quest listener initialized (Phase 3)")

        # Phase 4: Dialogue generation
        _dialogue_generator = FactionDialogueGenerator()
        _dialogue_generator.initialize()
        print("✓ Faction dialogue generator initialized (Phase 4)")

        # Phase 6: Advanced affinity features
        _tier_system = AffinityTierSystem()
        print("✓ Affinity tier system initialized (Phase 6)")

        _ripple_system = AffinityRippleSystem()
        _ripple_system.initialize(db)
        print("✓ Affinity ripple system initialized (Phase 6)")

        if enable_milestones:
            _milestone_system = AffinityMilestoneSystem()
            _milestone_system.initialize(db)
            print("✓ Affinity milestone system initialized (Phase 6)")

        if enable_decay:
            _decay_scheduler = AffinityDecayScheduler()
            _decay_scheduler.initialize(db)
            _decay_scheduler.start()
            print("✓ Affinity decay scheduler started (Phase 6)")

    except Exception as e:
        print(f"✗ Faction system initialization failed: {e}")
        raise


def get_dialogue_generator() -> Optional[FactionDialogueGenerator]:
    """Get the global FactionDialogueGenerator instance (Phase 4)."""
    return _dialogue_generator


def get_tier_system() -> Optional[AffinityTierSystem]:
    """Get the global AffinityTierSystem instance (Phase 6)."""
    return _tier_system


def get_ripple_system() -> Optional[AffinityRippleSystem]:
    """Get the global AffinityRippleSystem instance (Phase 6)."""
    return _ripple_system


def get_decay_scheduler() -> Optional[AffinityDecayScheduler]:
    """Get the global AffinityDecayScheduler instance (Phase 6)."""
    return _decay_scheduler


def get_milestone_system() -> Optional[AffinityMilestoneSystem]:
    """Get the global AffinityMilestoneSystem instance (Phase 6)."""
    return _milestone_system


def save_faction_systems() -> Dict[str, Any]:
    """Prepare faction state for save file.

    Returns:
        Minimal metadata (faction data persists in SQLite, not save file)
    """
    global _decay_scheduler

    try:
        # Stop decay scheduler before save to avoid mid-save mutations
        if _decay_scheduler:
            _decay_scheduler.stop()

        db = FactionDatabase.get_instance()
        # FactionDatabase persists automatically to faction.db in save directory
        # No additional save needed beyond database commits

        return {
            "version": 1,
            "systems_enabled": {
                "dialogue_generator": _dialogue_generator is not None,
                "tier_system": _tier_system is not None,
                "ripple_system": _ripple_system is not None,
                "decay_scheduler": _decay_scheduler is not None,
                "milestone_system": _milestone_system is not None,
            }
        }
    except Exception as e:
        print(f"⚠ Error saving faction state: {e}")
        return {}


def restore_faction_systems(save_data: Dict[str, Any]) -> None:
    """Restore faction database from save.

    Args:
        save_data: Dictionary from save file (contains system enabled flags)
    """
    global _decay_scheduler

    try:
        # Database connection persists across load cycles
        # No restoration needed—faction.db is already open

        # Restart decay scheduler if it was enabled
        if save_data.get("systems_enabled", {}).get("decay_scheduler"):
            if _decay_scheduler and not _decay_scheduler._running:
                _decay_scheduler.start()

    except Exception as e:
        print(f"⚠ Error restoring faction state: {e}")

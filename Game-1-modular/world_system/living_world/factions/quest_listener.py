"""Quest Event Listener for Faction System - Applies affinity deltas on quest completion.

Listens to QUEST_COMPLETED events from the GameEventBus and:
1. Retrieves NPC belonging tags (their affiliations)
2. Calculates affinity changes based on NPC-player relationship
3. Applies additive affinity deltas to player
4. Logs to WMS for consolidation

Usage:
    listener = FactionQuestListener()
    listener.initialize()  # Subscribes to QUEST_COMPLETED

    # Or automatically via game_engine._init_world_memory():
    from world_system.living_world.factions.quest_listener import FactionQuestListener
    FactionQuestListener.initialize_singleton()
"""

from __future__ import annotations

from typing import Optional, ClassVar
from events.event_bus import GameEvent, get_event_bus
from world_system.living_world.factions.database import FactionDatabase


class FactionQuestListener:
    """Listens to quest completion events and updates player affinity."""

    _instance: ClassVar[Optional[FactionQuestListener]] = None
    _initialized: bool = False

    def __init__(self):
        self._initialized = False

    @classmethod
    def get_instance(cls) -> FactionQuestListener:
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        if cls._instance:
            bus = get_event_bus()
            bus.unsubscribe("QUEST_COMPLETED", cls._instance.on_quest_completed)
        cls._instance = None

    def initialize(self) -> None:
        """Subscribe to quest completion events."""
        if self._initialized:
            return

        try:
            bus = get_event_bus()
            bus.subscribe("QUEST_COMPLETED", self.on_quest_completed, priority=10)
            self._initialized = True
            print("✓ FactionQuestListener initialized")
        except Exception as e:
            print(f"✗ FactionQuestListener init failed: {e}")
            raise

    @classmethod
    def initialize_singleton(cls) -> None:
        """Initialize the singleton instance (convenient entry point)."""
        listener = cls.get_instance()
        listener.initialize()

    def on_quest_completed(self, event: GameEvent) -> None:
        """Handle quest completion event.

        Args:
            event: GameEvent with keys:
                - quest_id: str
                - npc_id: str
                - quest_type: str
                - rewards: dict with experience, gold
        """
        try:
            quest_id = event.data.get("quest_id")
            npc_id = event.data.get("npc_id")

            if not quest_id or not npc_id:
                return  # Invalid event

            # Get faction database
            db = FactionDatabase.get_instance()
            if not db.connection or not db._initialized:
                return  # Faction DB not initialized

            # Get player from game engine (we need player_id)
            # This is tricky—we don't have direct access to the character
            # For now, we'll use a placeholder; the real implementation
            # should pass player_id in the event
            player_id = event.data.get("player_id")
            if not player_id:
                # Fallback: try to get from character (requires context)
                # For Phase 3, we assume player_id is added to the event
                return

            # Calculate and apply affinity changes
            self._apply_quest_affinity_changes(db, player_id, npc_id, quest_id)

        except Exception as e:
            print(f"⚠ Error in FactionQuestListener.on_quest_completed: {e}")

    def _apply_quest_affinity_changes(
        self, db: FactionDatabase, player_id: str, npc_id: str, quest_id: str
    ) -> None:
        """Apply affinity changes based on NPC affiliations.

        Args:
            db: FactionDatabase instance
            player_id: Player ID
            npc_id: NPC who gave the quest
            quest_id: Quest ID (for logging)
        """
        try:
            # Get NPC belonging tags (their affiliations)
            npc_tags = db.get_npc_belonging_tags(npc_id)
            if not npc_tags:
                return

            # Base affinity delta per tag (can be tuned)
            # Completing a quest for an NPC increases player affinity with all their tags
            base_delta = 10.0

            # Apply deltas for each NPC tag
            for tag in npc_tags:
                # Weight by significance (if NPC is deeply affiliated, reward is higher)
                # significance range: -100 to +100
                # Map to delta multiplier: 0.5 (for negative) to 1.5 (for positive)
                sig_multiplier = 1.0 + (tag.significance / 200.0)  # Range: 0.5 to 1.5
                delta = base_delta * max(0.5, sig_multiplier)  # Clamp at 0.5x minimum

                # Apply delta
                new_affinity = db.add_player_affinity_delta(
                    player_id, tag.tag, delta
                )

                print(
                    f"[Faction] Quest {quest_id}: +{delta:.1f} to {tag.tag} "
                    f"(now {new_affinity:.1f})"
                )

                # Log to WMS (via event) for consolidation
                # The WMS evaluator (FactionReputationEvaluator) will listen to this
                try:
                    bus = get_event_bus()
                    bus.publish(
                        "FACTION_AFFINITY_CHANGED",
                        {
                            "player_id": player_id,
                            "tag": tag.tag,
                            "delta": delta,
                            "new_value": new_affinity,
                            "source": "quest_completion",
                            "quest_id": quest_id,
                            "npc_id": npc_id,
                        },
                        source="FactionQuestListener",
                    )
                except Exception as e:
                    print(f"⚠ Error publishing FACTION_AFFINITY_CHANGED: {e}")

        except Exception as e:
            print(f"⚠ Error applying affinity changes: {e}")

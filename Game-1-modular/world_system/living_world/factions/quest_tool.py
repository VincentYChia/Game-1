"""Quest tool for affinity changes.

Provides an interface for quest system to apply affinity deltas to player
based on quest completion and player choices. Affinity changes are
automatically published to GameEventBus as FACTION_AFFINITY_CHANGED events.
"""

from typing import Dict

from .faction_system import FactionSystem


class QuestGenerator:
    """Generate and apply affinity deltas from quest outcomes."""

    @staticmethod
    def get_affinity_deltas(quest_id: str, choice_outcome: str) -> Dict[str, float]:
        """Get affinity delta map for a quest choice outcome.

        Args:
            quest_id: The quest ID (e.g., "smith_contract").
            choice_outcome: The outcome label (e.g., "complete_honestly").

        Returns:
            Dict mapping tag name to delta value (float). Can be empty if no deltas.

        Example:
            deltas = QuestGenerator.get_affinity_deltas("smith_contract", "complete_honestly")
            # Returns: {
            #     "guild:smiths": +15.0,
            #     "nation:stormguard": +10.0,
            #     "profession:blacksmith": +8.0,
            # }

        TODO: Load quest definitions from JSON or world_system tables
              to support arbitrary quests. For now, hardcoded examples.
        """
        quest_outcomes = {
            "smith_contract": {
                "complete_honestly": {
                    "guild:smiths": 15.0,
                    "nation:stormguard": 10.0,
                    "profession:blacksmith": 8.0,
                },
                "complete_dishonestly": {
                    "guild:smiths": -20.0,
                    "guild:thieves": 10.0,
                    "rank:criminal": 5.0,
                },
                "abandon": {
                    "guild:smiths": -10.0,
                    "rank:unreliable": 15.0,
                },
            },
            "merchant_trade": {
                "complete_fair": {
                    "guild:merchants": 12.0,
                    "nation:blackoak": 8.0,
                    "profession:merchant": 10.0,
                },
                "complete_cheated": {
                    "guild:merchants": -15.0,
                    "guild:thieves": 8.0,
                    "nation:blackoak": -20.0,
                },
            },
            "guard_patrol": {
                "complete_thorough": {
                    "profession:guard": 20.0,
                    "nation:stormguard": 15.0,
                    "rank:hero": 5.0,
                },
                "complete_lazy": {
                    "profession:guard": -10.0,
                    "nation:stormguard": -15.0,
                },
            },
        }

        quest_map = quest_outcomes.get(quest_id, {})
        return quest_map.get(choice_outcome, {})

    @staticmethod
    def apply_quest_deltas(player_id: str, deltas: Dict[str, float], game_time: float = 0.0) -> None:
        """Apply affinity delta dict to player.

        Each delta is applied via FactionSystem.adjust_player_affinity(),
        which publishes a FACTION_AFFINITY_CHANGED event for each tag.

        Args:
            player_id: The player's unique ID.
            deltas: Dict mapping tag to delta value.
            game_time: Game time for event timestamps (default 0.0).
        """
        fs = FactionSystem.get_instance()
        for tag, delta in deltas.items():
            fs.adjust_player_affinity(player_id, tag, delta, game_time)

    @staticmethod
    def apply_quest_completion(
        player_id: str,
        quest_id: str,
        choice_outcome: str,
        game_time: float = 0.0
    ) -> Dict[str, float]:
        """Apply all affinity changes for a quest completion.

        Convenience method combining get_affinity_deltas + apply_quest_deltas.

        Args:
            player_id: The player's unique ID.
            quest_id: The quest ID.
            choice_outcome: The choice outcome.
            game_time: Game time for event timestamps.

        Returns:
            The applied deltas (for logging/debugging).
        """
        deltas = QuestGenerator.get_affinity_deltas(quest_id, choice_outcome)
        if deltas:
            QuestGenerator.apply_quest_deltas(player_id, deltas, game_time)
        return deltas

    # Generic turn-in deltas (2026-07-11 affinity audit). The per-quest
    # outcome map above only knows three hand-written example quests, so
    # in practice NO live quest ever moved affinity — quest turn-in was
    # affinity-silent, which is invisible in a short test and glaring
    # after hours of play. These defaults are deliberately modest;
    # designer owns real economy.
    NPC_TURN_IN_DELTA = 5.0        # giver NPC toward player (-100..100)
    FACTION_PRIMARY_DELTA = 4.0    # giver's most significant tag
    FACTION_SECONDARY_DELTA = 2.0  # up to two further tags
    MAX_FACTION_TAGS = 3

    @staticmethod
    def apply_turn_in(
        player_id: str,
        giver_npc_id: str,
        quest_id: str = "",
        game_time: float = 0.0,
        explicit_deltas: Dict[str, float] = None,
    ) -> Dict[str, float]:
        """Apply affinity for ANY quest turn-in (the runtime entry point).

        Resolution order for the player→faction deltas:
        1. ``explicit_deltas`` (e.g. carried on a generated quest_def),
        2. the hand-written per-quest outcome map (``complete`` outcome),
        3. derived from the giver NPC's belonging tags (primary tag by
           significance gets FACTION_PRIMARY_DELTA, next two get
           FACTION_SECONDARY_DELTA).

        Always: the giver NPC's affinity toward the player rises by
        NPC_TURN_IN_DELTA, and the consolidated player standing is
        recomputed + published (FACTION_AFFINITY_CONSOLIDATED — the
        consolidator previously had no caller at all).

        Best-effort: returns the applied delta map; failures return {}.
        """
        try:
            fs = FactionSystem.get_instance()
        except Exception:
            return {}

        deltas: Dict[str, float] = dict(explicit_deltas or {})
        if not deltas and quest_id:
            deltas = QuestGenerator.get_affinity_deltas(quest_id, "complete")
        if not deltas and giver_npc_id:
            try:
                tags = fs.get_npc_belonging_tags(giver_npc_id)
            except Exception:
                tags = []
            tags = sorted(tags, key=lambda t: -getattr(t, "significance", 0.0))
            for i, tag in enumerate(tags[:QuestGenerator.MAX_FACTION_TAGS]):
                deltas[tag.tag] = (QuestGenerator.FACTION_PRIMARY_DELTA
                                   if i == 0 else
                                   QuestGenerator.FACTION_SECONDARY_DELTA)

        try:
            if deltas:
                QuestGenerator.apply_quest_deltas(player_id, deltas, game_time)
            if giver_npc_id:
                fs.adjust_npc_affinity_toward_player(
                    npc_id=giver_npc_id,
                    delta=QuestGenerator.NPC_TURN_IN_DELTA,
                    game_time=game_time,
                )
        except Exception:
            return deltas

        try:
            from .consolidator import AffinityConsolidator
            AffinityConsolidator.consolidate_and_publish(player_id)
        except Exception:
            pass
        return deltas

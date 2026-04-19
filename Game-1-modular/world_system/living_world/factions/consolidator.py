"""Affinity consolidator for narrative-friendly summaries.

Provides aggregation methods to roll up affinity changes into high-level
narratives suitable for WMS Layer 3-4 events. Publishes consolidated
summaries for story generation systems.
"""

from typing import Dict

from events.event_bus import get_event_bus

from .faction_system import FactionSystem

FACTION_AFFINITY_CONSOLIDATED = "FACTION_AFFINITY_CONSOLIDATED"


class AffinityConsolidator:
    """Consolidate affinity data into narrative-friendly aggregations."""

    @staticmethod
    def consolidate_player_standing(player_id: str) -> Dict[str, float]:
        """Get top 5 tags by affinity for player.

        Useful for generating narrative summaries of player reputation.
        Filters out zero/near-zero values.

        Args:
            player_id: The player's unique ID.

        Returns:
            Dict of {tag: affinity_value} for top 5 tags by affinity,
            sorted by absolute value descending. Returns empty dict if no affinities.

        Example:
            standing = AffinityConsolidator.consolidate_player_standing("player_1")
            # Returns:
            # {
            #     "guild:smiths": 75.0,
            #     "nation:stormguard": 60.0,
            #     "profession:blacksmith": 50.0,
            #     "rank:hero": 45.0,
            #     "guild:merchants": -40.0,
            # }
        """
        fs = FactionSystem.get_instance()
        aff = fs.get_all_player_affinities(player_id)

        # Filter zero values
        nonzero = {tag: val for tag, val in aff.items() if val != 0.0}

        # Sort by absolute value descending
        sorted_aff = sorted(
            nonzero.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )

        # Take top 5
        return dict(sorted_aff[:5])

    @staticmethod
    def get_player_reputation_summary(player_id: str) -> str:
        """Generate a one-liner reputation summary.

        Args:
            player_id: The player's unique ID.

        Returns:
            Human-readable summary string, e.g.,
            "Revered by smiths, distrusted by merchants".
        """
        standing = AffinityConsolidator.consolidate_player_standing(player_id)
        if not standing:
            return "Unknown reputation"

        parts = []
        for tag, value in standing.items():
            if value > 50:
                sentiment = "revered"
            elif value > 0:
                sentiment = "well-regarded"
            elif value < -50:
                sentiment = "distrusted"
            else:
                sentiment = "disliked"
            parts.append(f"{sentiment} by {tag}")

        return ", ".join(parts)

    @staticmethod
    def publish_consolidated_event(player_id: str, summary: Dict[str, float]) -> None:
        """Publish consolidated summary to GameEventBus.

        Allows WMS Layer 3-4 evaluators to consume high-level affinity
        summaries for narrative generation.

        Args:
            player_id: The player's unique ID.
            summary: Dict of {tag: affinity_value} (typically from consolidate_player_standing).

        Example:
            standing = AffinityConsolidator.consolidate_player_standing("player_1")
            AffinityConsolidator.publish_consolidated_event("player_1", standing)
        """
        try:
            event_bus = get_event_bus()
            event_bus.publish(
                FACTION_AFFINITY_CONSOLIDATED,
                {
                    "player_id": player_id,
                    "top_affinities": summary,
                },
                source="AffinityConsolidator"
            )
        except Exception as e:
            print(f"[Consolidator] Publish failed: {e}")

    @staticmethod
    def consolidate_and_publish(player_id: str) -> Dict[str, float]:
        """Convenience method: consolidate standing and publish event.

        Args:
            player_id: The player's unique ID.

        Returns:
            The consolidated standing dict.
        """
        standing = AffinityConsolidator.consolidate_player_standing(player_id)
        if standing:
            AffinityConsolidator.publish_consolidated_event(player_id, standing)
        return standing

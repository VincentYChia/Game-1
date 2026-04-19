"""Helper to assemble dialogue context from FactionSystem.

Used by NPC dialogue generation to build affinity-aware context
for BackendManager LLM calls.
"""

from typing import Any, Dict, List, Optional, Tuple

from .faction_system import FactionSystem


def assemble_dialogue_context(
    npc_id: str,
    player_id: str,
    location_hierarchy: List[Tuple[str, Optional[str]]],
) -> Dict[str, Any]:
    """Assemble dialogue context from faction data.

    Args:
        npc_id: The NPC to get context for.
        player_id: The player interacting with the NPC.
        location_hierarchy: List of (tier, location_id) tuples representing
                          the geographic hierarchy (e.g., [("locality", "westhollow"),
                          ("district", "iron_hills"), ("nation", "nation:stormguard"),
                          ("world", None)]).

    Returns:
        Dict with keys: npc, player, npc_opinion, location.
        Ready to pass to BackendManager.generate().
    """
    fs = FactionSystem.get_instance()

    # Get NPC profile
    npc = fs.get_npc_profile(npc_id)

    # Get player's affinities with all tags
    player_aff = fs.get_all_player_affinities(player_id)

    # Get NPC's personal opinion of the player
    npc_opinion = fs.get_npc_affinity_toward_player(npc_id)

    # Get location affinity defaults (inherited from hierarchy)
    location = fs.compute_inherited_affinity(location_hierarchy)

    return {
        "npc": npc,
        "player": {"id": player_id, "affinity_with_tags": player_aff},
        "npc_opinion": npc_opinion,
        "location": location,
    }

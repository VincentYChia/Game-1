"""Faction System Data Models — Phase 2: NPC + Player Profiles, Affinity, Tags.

Core dataclasses:
- FactionTag: A belonging tag with significance and narrative hooks
- NPCProfile: NPC with narrative, belonging tags, and affinity toward other tags
- PlayerProfile: Player's affinities with all tags
- LocationAffinityDefault: Cultural affinity default for a geographic address

NPC personal affinity toward the player is NOT a separate dataclass — it is
stored in the `npc_affinity` table using the reserved tag
``NPC_AFFINITY_PLAYER_TAG`` (see schema.py). Read via
``FactionSystem.get_npc_affinity_toward_player(npc_id)``.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class FactionTag:
    """A single belonging tag on an NPC."""
    tag: str                                           # e.g., "nation:stormguard"
    significance: float                                # 0.0-1.0 (Nominal to Nucleus)
    role: Optional[str] = None                         # e.g., "soldier", "elder", "member"
    narrative_hooks: List[str] = field(default_factory=list)
    since_game_time: float = 0.0


@dataclass
class NPCProfile:
    """Complete NPC faction profile.

    Stores narrative, belonging tags (which factions define them), and
    personal affinity (-100 to 100) toward other tags.
    """
    npc_id: str
    narrative: str
    created_at: float
    last_updated: float

    belonging_tags: Dict[str, FactionTag] = field(default_factory=dict)  # tag → FactionTag
    affinity: Dict[str, float] = field(default_factory=dict)             # tag → -100..100

    def add_tag(self, tag: str, significance: float, role: Optional[str] = None,
                narrative_hooks: Optional[List[str]] = None, game_time: float = 0.0) -> None:
        """Add or update a belonging tag."""
        self.belonging_tags[tag] = FactionTag(
            tag=tag,
            significance=significance,
            role=role,
            narrative_hooks=narrative_hooks or [],
            since_game_time=game_time,
        )

    def set_affinity(self, tag: str, value: float) -> None:
        self.affinity[tag] = max(-100.0, min(100.0, value))

    def adjust_affinity(self, tag: str, delta: float) -> float:
        current = self.affinity.get(tag, 0.0)
        new_value = max(-100.0, min(100.0, current + delta))
        self.affinity[tag] = new_value
        return new_value

    def get_affinity(self, tag: str) -> float:
        return self.affinity.get(tag, 0.0)


@dataclass
class PlayerProfile:
    """Player's faction affinity profile (tag → -100..100)."""
    player_id: str
    affinity: Dict[str, float] = field(default_factory=dict)

    def set_affinity(self, tag: str, value: float) -> None:
        self.affinity[tag] = max(-100.0, min(100.0, value))

    def adjust_affinity(self, tag: str, delta: float) -> float:
        current = self.affinity.get(tag, 0.0)
        new_value = max(-100.0, min(100.0, current + delta))
        self.affinity[tag] = new_value
        return new_value

    def get_affinity(self, tag: str) -> float:
        return self.affinity.get(tag, 0.0)


@dataclass
class LocationAffinityDefault:
    """Cultural affinity default for a location.

    Cultural baseline for how a location feels about a tag.
    Stored sparsely: only non-zero values.
    Inherited hierarchically: locality → district → province → region → nation → world.
    """
    address_tier: str                # "world", "nation", "region", "province", "district", "locality"
    location_id: Optional[str]       # e.g., "nation:stormguard"; None for world tier
    tag: str                         # e.g., "guild:merchants"
    affinity_value: float            # -100 to 100

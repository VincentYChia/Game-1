"""Faction System Data Models — Phase 2: NPC + Player Profiles, Affinity, Tags.

Core dataclasses for the corrected faction system:
- FactionTag: A tag with significance and narrative hooks
- NPCProfile: NPC with narrative, belonging tags, and affinity toward other tags
- PlayerProfile: Player's affinities with all tags
- LocationAffinityDefault: Cultural affinity defaults for a geographic address
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class FactionTag:
    """A single faction tag belonging to an NPC."""
    tag: str                           # e.g., "nation:stormguard"
    significance: float                # 0.0-1.0 (Nominal to Nucleus)
    role: Optional[str] = None         # e.g., "soldier", "elder", "member"
    narrative_hooks: List[str] = field(default_factory=list)  # ≥1 specific facts
    since_game_time: float = 0.0


@dataclass
class NPCProfile:
    """Complete NPC faction profile.

    Stores NPC narrative, their belonging tags (which factions define them),
    and their personal affinity toward other tags.
    """
    npc_id: str
    narrative: str                     # Full background/personality
    created_at: float                  # Game time of creation
    last_updated: float                # Game time of last update

    # Belonging: which tags define this NPC (with significance)
    belonging_tags: Dict[str, FactionTag] = field(default_factory=dict)  # tag → FactionTag

    # Affinity: how this NPC feels about other tags (-100 to 100)
    affinity: Dict[str, float] = field(default_factory=dict)  # tag → affinity

    def add_tag(self, tag: str, significance: float, role: Optional[str] = None,
                narrative_hooks: Optional[List[str]] = None, game_time: float = 0.0) -> None:
        """Add or update a belonging tag."""
        self.belonging_tags[tag] = FactionTag(
            tag=tag,
            significance=significance,
            role=role,
            narrative_hooks=narrative_hooks or [],
            since_game_time=game_time
        )

    def set_affinity(self, tag: str, value: float) -> None:
        """Set NPC's affinity with a tag (-100 to 100)."""
        self.affinity[tag] = max(-100.0, min(100.0, value))

    def adjust_affinity(self, tag: str, delta: float) -> float:
        """Adjust affinity by delta, return new value."""
        current = self.affinity.get(tag, 0.0)
        new_value = max(-100.0, min(100.0, current + delta))
        self.affinity[tag] = new_value
        return new_value

    def get_affinity(self, tag: str) -> float:
        """Get affinity with a tag (default 0)."""
        return self.affinity.get(tag, 0.0)


@dataclass
class PlayerProfile:
    """Player's faction affinity profile.

    Stores player's affinity (-100 to 100) with all tags.
    Separate from NPC profiles; only tracks player's standing.
    """
    player_id: str
    affinity: Dict[str, float] = field(default_factory=dict)  # tag → affinity

    def set_affinity(self, tag: str, value: float) -> None:
        """Set affinity with a tag (-100 to 100)."""
        self.affinity[tag] = max(-100.0, min(100.0, value))

    def adjust_affinity(self, tag: str, delta: float) -> float:
        """Adjust affinity by delta, return new value."""
        current = self.affinity.get(tag, 0.0)
        new_value = max(-100.0, min(100.0, current + delta))
        self.affinity[tag] = new_value
        return new_value

    def get_affinity(self, tag: str) -> float:
        """Get affinity with a tag (default 0)."""
        return self.affinity.get(tag, 0.0)


@dataclass
class LocationAffinityDefault:
    """Cultural affinity default for a location.

    Cultural baseline for how a location feels about a tag.
    Stored sparsely: only non-zero values.
    Inherited hierarchically: locality → district → region → nation → world.
    """
    address_tier: str                  # "world", "nation", "region", "province", "district", "locality"
    location_id: str                   # e.g., "nation:stormguard", NULL for world
    tag: str                           # e.g., "guild:merchants"
    affinity: float                    # -100 to 100 (cultural default for this tag at this location)


@dataclass
class NPCAffinityTowardPlayer:
    """How an individual NPC personally feels about the player.

    Separate from player's global affinity with NPC's tags.
    This is per-NPC personal opinion, independent of tag-based standing.
    """
    npc_id: str
    affinity: float                    # -100 to 100 (how this NPC feels about the player)

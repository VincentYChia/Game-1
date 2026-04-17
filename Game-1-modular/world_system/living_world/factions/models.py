"""Faction System Data Models - NPC profiles, player affinity, belonging tags.

Core dataclasses for the faction system. These mirror the SQLite schema
and are used for in-memory representation during gameplay.

Usage:
    npc_profile = NPCFactionProfile(
        npc_id="npc_1",
        location_id="village_westhollow",
        narrative="A blacksmith in a small village...",
        primary_tag="profession:blacksmith",
        created_at=1000.0,
        last_updated=1000.0
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time


@dataclass
class NPCBelongingTag:
    """Single belonging tag for an NPC."""
    tag: str                           # e.g., "nation:stormguard"
    significance: float                # -100 to 100 or bucket name
    role: Optional[str] = None         # e.g., "guard", "elder", "member"
    narrative_hooks: List[str] = field(default_factory=list)  # >=3 bullet points


@dataclass
class NPCFactionProfile:
    """Complete NPC faction profile - stored in npc_profiles table.

    Represents an NPC's narrative identity, belonging tags, and metadata.
    Affinity is derived at query time from address + cultural_affinity_cache.
    """
    npc_id: str
    location_id: str                   # Resolves to full address (world → locality)
    narrative: str                     # Full background, can evolve
    primary_tag: str                   # Main identity (e.g., "profession:blacksmith")
    created_at: float                  # Game time of creation
    last_updated: float                # Game time of last update

    # Optional metadata
    metadata: Dict = field(default_factory=dict)  # Extensible: archetype, version, etc.

    # Note: belonging_tags are stored separately in npc_belonging table
    # They're not stored here to avoid duplicate data and improve queryability

    def age_in_game_time(self, current_time: float) -> float:
        """How long ago was this NPC created?"""
        return current_time - self.created_at

    def time_since_update(self, current_time: float) -> float:
        """How long since this NPC was last updated?"""
        return current_time - self.last_updated


@dataclass
class PlayerAffinityProfile:
    """Player's affinity with tags (-100 to +100).

    Represents player's earned reputation with factions, guilds, nations, etc.
    Starts at 0, changes via quests and interactions.
    Stored in player_affinity table.
    """
    player_id: str
    affinity: Dict[str, float] = field(default_factory=dict)  # tag → current_value

    def get_affinity(self, tag: str) -> float:
        """Get player's current affinity with a tag (default 0)."""
        return self.affinity.get(tag, 0.0)

    def add_delta(self, tag: str, delta: float) -> float:
        """Apply affinity delta (additive, not replacement).

        Args:
            tag: Tag to modify
            delta: Amount to add (negative = decrease)

        Returns:
            New affinity value for the tag (clamped to -100 to 100)
        """
        current = self.affinity.get(tag, 0.0)
        new_value = max(-100.0, min(100.0, current + delta))
        self.affinity[tag] = new_value
        return new_value

    def set_affinity(self, tag: str, value: float) -> None:
        """Set affinity directly (clamped to -100 to 100)."""
        self.affinity[tag] = max(-100.0, min(100.0, value))


@dataclass
class AffinityDefaultEntry:
    """Single entry in affinity_defaults table.

    Represents how much a location (at a specific tier) feels toward a tag.
    Multiple entries sum to create NPC cultural affinity.
    """
    tier: str              # "world", "nation", "region", "province", "district", "locality"
    location_id: str       # e.g., "nation:stormguard" or NULL for world
    tag: str               # e.g., "guild:merchants"
    delta: float           # -100 to 100


@dataclass
class CulturalAffinityEntry:
    """Single entry in cultural_affinity_cache table.

    Pre-calculated cultural affinity for efficiency.
    Built from affinity_defaults, updated only when defaults change.
    """
    tier: str              # "world", "nation", "region", "province", "district", "locality"
    location_id: str       # e.g., "nation:stormguard"
    tag: str               # e.g., "guild:merchants"
    cultural_affinity: float  # Pre-summed value


@dataclass
class QuestLogEntry:
    """Single quest log entry - NPC interaction tracking."""
    player_id: str
    quest_id: str
    npc_id: str
    status: str            # "offered", "in_progress", "completed", "failed"
    offered_at: float      # Game time when quest was offered
    completed_at: Optional[float] = None  # Game time when completed


@dataclass
class NPCContextForDialogue:
    """Assembled context for LLM dialogue generation.

    Combines NPC profile, cultural affinity, and player affinity
    into a single context dict for the LLM.
    """
    npc_id: str
    npc_narrative: str
    npc_primary_tag: str
    npc_belonging_tags: List[NPCBelongingTag]
    npc_cultural_affinity: Dict[str, float]  # tag → cultural_affinity

    player_id: str
    player_affinity: Dict[str, float]        # tag → player_affinity

    # Metadata for dialogue enrichment
    quest_history: List[QuestLogEntry] = field(default_factory=list)
    location_id: str = ""

    def to_dict(self) -> Dict:
        """Convert to dict for JSON serialization or LLM prompting."""
        return {
            "npc_id": self.npc_id,
            "npc_narrative": self.npc_narrative,
            "npc_primary_tag": self.npc_primary_tag,
            "npc_belonging_tags": [
                {
                    "tag": tag.tag,
                    "significance": tag.significance,
                    "role": tag.role,
                    "narrative_hooks": tag.narrative_hooks
                }
                for tag in self.npc_belonging_tags
            ],
            "npc_cultural_affinity": self.npc_cultural_affinity,
            "player_affinity": self.player_affinity,
            "quest_history": [
                {
                    "quest_id": q.quest_id,
                    "status": q.status,
                    "completed_at": q.completed_at
                }
                for q in self.quest_history
            ],
            "location_id": self.location_id
        }

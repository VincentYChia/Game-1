"""NPCMemory — persistent per-NPC memory for the Living World.

Each NPC maintains:
- Relationship score with the player (-1.0 to 1.0)
- Emotional state (neutral, happy, angry, etc.)
- Knowledge: compressed one-line summaries of world events
- Conversation summary: rolling summary of past dialogues
- Reputation tags: labels the NPC associates with the player
- Quest state: per-quest tracking

NPCMemory is stored in SQLite (via EventStore) and restored on load.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional


@dataclass
class NPCMemory:
    """Persistent memory state for a single NPC."""

    npc_id: str
    relationship_score: float = 0.0         # -1.0 (hostile) to 1.0 (devoted)
    interaction_count: int = 0              # Total conversations
    last_interaction_time: float = 0.0      # Game time of last interaction
    emotional_state: str = "neutral"        # Current emotion
    knowledge: List[str] = field(default_factory=list)  # One-line event summaries
    conversation_summary: str = ""          # Compressed dialogue history
    player_reputation_tags: List[str] = field(default_factory=list)
    quest_state: Dict[str, str] = field(default_factory=dict)  # quest_id → state

    # Limits (loaded from config)
    _max_knowledge: int = 30
    _max_summary_length: int = 500
    _max_reputation_tags: int = 10

    def add_knowledge(self, fact: str) -> None:
        """Add a knowledge fact, trimming oldest if over limit."""
        if fact in self.knowledge:
            return
        self.knowledge.append(fact)
        if len(self.knowledge) > self._max_knowledge:
            self.knowledge = self.knowledge[-self._max_knowledge:]

    def adjust_relationship(self, delta: float) -> float:
        """Adjust relationship score, clamping to [-1.0, 1.0].

        Returns the new relationship score.
        """
        self.relationship_score = max(-1.0, min(1.0,
            self.relationship_score + delta
        ))
        return self.relationship_score

    def set_emotion(self, emotion: str) -> None:
        """Update the NPC's emotional state."""
        self.emotional_state = emotion

    def add_reputation_tag(self, tag: str) -> None:
        """Add a reputation tag the NPC associates with the player."""
        if tag not in self.player_reputation_tags:
            self.player_reputation_tags.append(tag)
            if len(self.player_reputation_tags) > self._max_reputation_tags:
                self.player_reputation_tags = self.player_reputation_tags[-self._max_reputation_tags:]

    def get_relationship_label(self, thresholds: Optional[Dict[str, float]] = None) -> str:
        """Get a human-readable relationship label."""
        t = thresholds or {
            "hostile": -0.75, "unfriendly": -0.25,
            "neutral_low": -0.1, "neutral_high": 0.1,
            "friendly": 0.25, "trusted": 0.5, "devoted": 0.75,
        }
        score = self.relationship_score
        if score <= t.get("hostile", -0.75):
            return "hostile"
        if score <= t.get("unfriendly", -0.25):
            return "unfriendly"
        if score <= t.get("neutral_high", 0.1):
            return "neutral"
        if score <= t.get("friendly", 0.25):
            return "friendly"
        if score <= t.get("trusted", 0.5):
            return "trusted"
        if score <= t.get("devoted", 0.75):
            return "devoted"
        return "devoted"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for SQLite/save persistence."""
        return {
            "npc_id": self.npc_id,
            "relationship_score": self.relationship_score,
            "interaction_count": self.interaction_count,
            "last_interaction_time": self.last_interaction_time,
            "emotional_state": self.emotional_state,
            "knowledge": list(self.knowledge),
            "conversation_summary": self.conversation_summary,
            "player_reputation_tags": list(self.player_reputation_tags),
            "quest_state": dict(self.quest_state),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NPCMemory:
        """Restore from serialized data."""
        return cls(
            npc_id=data.get("npc_id", "unknown"),
            relationship_score=data.get("relationship_score", 0.0),
            interaction_count=data.get("interaction_count", 0),
            last_interaction_time=data.get("last_interaction_time", 0.0),
            emotional_state=data.get("emotional_state", "neutral"),
            knowledge=data.get("knowledge", []),
            conversation_summary=data.get("conversation_summary", ""),
            player_reputation_tags=data.get("player_reputation_tags", []),
            quest_state=data.get("quest_state", {}),
        )


class NPCMemoryManager:
    """Manages NPCMemory instances for all NPCs. Singleton."""

    _instance: ClassVar[Optional[NPCMemoryManager]] = None

    def __init__(self):
        self._memories: Dict[str, NPCMemory] = {}
        self._config: Dict[str, Any] = {}
        self._initialized: bool = False

    @classmethod
    def get_instance(cls) -> NPCMemoryManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize with config from npc-personalities.json."""
        if self._initialized:
            return
        self._config = config or {}
        limits = self._config.get("memory_limits", {})
        self._max_knowledge = limits.get("max_knowledge_items", 30)
        self._max_summary = limits.get("max_conversation_summary_length", 500)
        self._max_tags = limits.get("max_reputation_tags", 10)
        self._initialized = True

    def get_memory(self, npc_id: str) -> NPCMemory:
        """Get or create memory for an NPC."""
        if npc_id not in self._memories:
            mem = NPCMemory(npc_id=npc_id)
            mem._max_knowledge = self._max_knowledge if self._initialized else 30
            mem._max_summary_length = self._max_summary if self._initialized else 500
            mem._max_reputation_tags = self._max_tags if self._initialized else 10
            self._memories[npc_id] = mem
        return self._memories[npc_id]

    def get_all_memories(self) -> Dict[str, NPCMemory]:
        """Get all NPC memories."""
        return dict(self._memories)

    def save_all(self) -> Dict[str, Dict[str, Any]]:
        """Serialize all NPC memories for persistence."""
        return {npc_id: mem.to_dict() for npc_id, mem in self._memories.items()}

    def load_all(self, data: Dict[str, Dict[str, Any]]) -> None:
        """Restore all NPC memories from saved data."""
        for npc_id, mem_data in data.items():
            self._memories[npc_id] = NPCMemory.from_dict(mem_data)

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "npc_count": len(self._memories),
            "npcs_with_interactions": sum(
                1 for m in self._memories.values() if m.interaction_count > 0
            ),
        }

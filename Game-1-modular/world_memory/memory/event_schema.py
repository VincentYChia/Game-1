"""Event schema definitions for the World Memory System.

Layer 2: WorldMemoryEvent — atomic structured facts stored in SQLite.
Layer 3: InterpretedEvent — narrative descriptions derived from patterns.

All dataclasses here are pure data with no dependencies on game systems.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class EventType(Enum):
    """All trackable event types. Maps to GameEventBus event names."""

    # Combat
    ATTACK_PERFORMED = "attack_performed"
    DAMAGE_TAKEN = "damage_taken"
    ENEMY_KILLED = "enemy_killed"
    PLAYER_DEATH = "player_death"
    DODGE_PERFORMED = "dodge_performed"
    STATUS_APPLIED = "status_applied"

    # Gathering
    RESOURCE_GATHERED = "resource_gathered"
    NODE_DEPLETED = "node_depleted"

    # Crafting
    CRAFT_ATTEMPTED = "craft_attempted"
    ITEM_INVENTED = "item_invented"
    RECIPE_DISCOVERED = "recipe_discovered"

    # Economy / Inventory
    ITEM_ACQUIRED = "item_acquired"
    ITEM_CONSUMED = "item_consumed"
    ITEM_EQUIPPED = "item_equipped"
    REPAIR_PERFORMED = "repair_performed"

    # Progression
    LEVEL_UP = "level_up"
    SKILL_LEARNED = "skill_learned"
    SKILL_USED = "skill_used"
    TITLE_EARNED = "title_earned"
    CLASS_CHANGED = "class_changed"

    # Exploration
    CHUNK_ENTERED = "chunk_entered"
    AREA_DISCOVERED = "area_discovered"

    # Social
    NPC_INTERACTION = "npc_interaction"
    QUEST_ACCEPTED = "quest_accepted"
    QUEST_COMPLETED = "quest_completed"
    QUEST_FAILED = "quest_failed"

    # World / System
    WORLD_EVENT = "world_event"
    POSITION_SAMPLE = "position_sample"


# Bus event names that map to memory event types
BUS_TO_MEMORY_TYPE = {
    "DAMAGE_DEALT": EventType.ATTACK_PERFORMED,
    "PLAYER_HIT": EventType.DAMAGE_TAKEN,
    "ENEMY_KILLED": EventType.ENEMY_KILLED,
    "PLAYER_DIED": EventType.PLAYER_DEATH,
    "DODGE_PERFORMED": EventType.DODGE_PERFORMED,
    "STATUS_APPLIED": EventType.STATUS_APPLIED,
    "RESOURCE_GATHERED": EventType.RESOURCE_GATHERED,
    "NODE_DEPLETED": EventType.NODE_DEPLETED,
    "ITEM_CRAFTED": EventType.CRAFT_ATTEMPTED,
    "ITEM_INVENTED": EventType.ITEM_INVENTED,
    "RECIPE_DISCOVERED": EventType.RECIPE_DISCOVERED,
    "ITEM_ACQUIRED": EventType.ITEM_ACQUIRED,
    "ITEM_EQUIPPED": EventType.ITEM_EQUIPPED,
    "EQUIPMENT_CHANGED": EventType.ITEM_EQUIPPED,
    "REPAIR_PERFORMED": EventType.REPAIR_PERFORMED,
    "LEVEL_UP": EventType.LEVEL_UP,
    "SKILL_LEARNED": EventType.SKILL_LEARNED,
    "SKILL_ACTIVATED": EventType.SKILL_USED,
    "TITLE_EARNED": EventType.TITLE_EARNED,
    "CLASS_CHANGED": EventType.CLASS_CHANGED,
    "CHUNK_ENTERED": EventType.CHUNK_ENTERED,
    "AREA_DISCOVERED": EventType.AREA_DISCOVERED,
    "NPC_INTERACTION": EventType.NPC_INTERACTION,
    "QUEST_ACCEPTED": EventType.QUEST_ACCEPTED,
    "QUEST_COMPLETED": EventType.QUEST_COMPLETED,
    "QUEST_FAILED": EventType.QUEST_FAILED,
    "WORLD_EVENT": EventType.WORLD_EVENT,
    "POSITION_SAMPLE": EventType.POSITION_SAMPLE,
}

# Bus events to skip (visual-only, high-frequency noise)
SKIP_BUS_EVENTS = frozenset({
    "SCREEN_SHAKE",
    "PARTICLE_BURST",
    "FLASH_ENTITY",
    "ATTACK_PHASE",
    "ATTACK_STARTED",
})


@dataclass
class WorldMemoryEvent:
    """Atomic unit of world memory — one thing that happened.

    This is a Layer 2 record: an immutable structured fact.
    """

    # Identity
    event_id: str
    event_type: str
    event_subtype: str

    # WHO
    actor_id: str
    actor_type: str
    target_id: Optional[str] = None
    target_type: Optional[str] = None

    # WHERE
    position_x: float = 0.0
    position_y: float = 0.0
    chunk_x: int = 0
    chunk_y: int = 0
    locality_id: Optional[str] = None
    district_id: Optional[str] = None
    province_id: Optional[str] = None
    biome: str = "unknown"

    # WHEN
    game_time: float = 0.0
    real_time: float = field(default_factory=time.time)
    session_id: str = ""

    # WHAT HAPPENED
    magnitude: float = 0.0
    result: str = "success"
    quality: Optional[str] = None
    tier: Optional[int] = None

    # TAGS for interest matching
    tags: List[str] = field(default_factory=list)

    # CONTEXT (event-specific flexible data)
    context: Dict[str, Any] = field(default_factory=dict)

    # INTERPRETATION TRACKING
    interpretation_count: int = 0
    triggered_interpretation: bool = False

    @staticmethod
    def create(event_type: str, event_subtype: str,
               actor_id: str, actor_type: str = "player",
               **kwargs) -> WorldMemoryEvent:
        """Factory for creating events with auto-generated ID."""
        return WorldMemoryEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            event_subtype=event_subtype,
            actor_id=actor_id,
            actor_type=actor_type,
            real_time=time.time(),
            **kwargs,
        )


@dataclass
class InterpretedEvent:
    """A narrative description derived from Layer 2 patterns. Layer 3.

    These are the "news stories" of the world: pattern-detected,
    threshold-triggered text descriptions. NOT JSON game effects.
    """

    # Identity
    interpretation_id: str
    created_at: float  # Game time

    # THE NARRATIVE — core output
    narrative: str

    # Classification
    category: str  # population_change, resource_pressure, player_milestone, etc.
    severity: str  # minor, moderate, significant, major, critical

    # What triggered this
    trigger_event_id: str
    trigger_count: int
    cause_event_ids: List[str] = field(default_factory=list)

    # Spatial scope
    affected_locality_ids: List[str] = field(default_factory=list)
    affected_district_ids: List[str] = field(default_factory=list)
    affected_province_ids: List[str] = field(default_factory=list)
    epicenter_x: float = 0.0
    epicenter_y: float = 0.0

    # What this concerns (for routing to interested entities)
    affects_tags: List[str] = field(default_factory=list)

    # Duration
    is_ongoing: bool = False
    expires_at: Optional[float] = None

    # History tracking
    supersedes_id: Optional[str] = None
    update_count: int = 1
    archived: bool = False

    @staticmethod
    def create(narrative: str, category: str, severity: str,
               trigger_event_id: str, trigger_count: int,
               game_time: float, **kwargs) -> InterpretedEvent:
        """Factory for creating interpretations with auto-generated ID."""
        return InterpretedEvent(
            interpretation_id=str(uuid.uuid4()),
            created_at=game_time,
            narrative=narrative,
            category=category,
            severity=severity,
            trigger_event_id=trigger_event_id,
            trigger_count=trigger_count,
            **kwargs,
        )


# Severity ordering for comparisons
SEVERITY_ORDER = {
    "minor": 0,
    "moderate": 1,
    "significant": 2,
    "major": 3,
    "critical": 4,
}

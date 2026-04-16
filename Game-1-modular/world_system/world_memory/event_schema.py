"""Event schema definitions for the World Memory System.

Raw Event Pipeline: WorldMemoryEvent — atomic structured facts stored in SQLite.
Layer 2: InterpretedEvent — narrative descriptions derived from patterns (evaluator output).
Layer 3: ConsolidatedEvent — cross-domain synthesis from Layer 2 (district/global scope).
Layer 4: ProvinceSummaryEvent — province-level summaries from Layer 3 (per-province scope).
Layer 5: RegionSummaryEvent — region-level summaries from Layer 4 (per-region scope, game Region tier).
Layer 6: NationSummaryEvent — nation-level summaries from Layer 5 (per-nation scope, game Nation tier).
Layer 7: WorldSummaryEvent — world-level summaries from Layer 6 (singleton game World tier).

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

    # Engineering / Defense / Exploration (new)
    FISH_CAUGHT = "fish_caught"
    CHEST_OPENED = "chest_opened"
    TURRET_PLACED = "turret_placed"
    BARRIER_PLACED = "barrier_placed"


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
    # New: fishing, chests, engineering/defense
    "FISH_CAUGHT": EventType.FISH_CAUGHT,
    "CHEST_OPENED": EventType.CHEST_OPENED,
    "TURRET_PLACED": EventType.TURRET_PLACED,
    "BARRIER_PLACED": EventType.BARRIER_PLACED,
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

    This is a raw event pipeline record: an immutable structured fact.
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
    # Full 6-tier address, populated by EventRecorder._enrich_geographic
    # from the event's chunk position. See
    # docs/ARCHITECTURAL_DECISIONS.md — address tags are FACTS, assigned
    # at capture from chunk position, never synthesized by an LLM.
    locality_id: Optional[str] = None   # Sparse — only if chunk has a POI
    district_id: Optional[str] = None   # Always present per chunk
    province_id: Optional[str] = None   # Always present per chunk
    region_id: Optional[str] = None     # Always present per chunk
    nation_id: Optional[str] = None     # Always present per chunk
    world_id: Optional[str] = None      # Always present (singleton)
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
    """A narrative description derived from raw event pipeline patterns. Layer 2.

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


@dataclass
class ConsolidatedEvent:
    """A cross-domain narrative synthesized from multiple Layer 2 interpretations.

    Layer 3 output. These are "connected interpretations" — they link
    multiple single-lens Layer 2 events into a coherent district-level
    or global picture. Stored in LayerStore layer3_events + layer3_tags.

    Categories:
    - regional_synthesis: overall district activity summary
    - cross_domain: patterns connecting different activity types
    - player_identity: behavioral profile from all player events
    - faction_narrative: faction relationship narrative
    """

    # Identity
    consolidation_id: str
    created_at: float  # Game time

    # THE NARRATIVE — core output
    narrative: str

    # Classification
    category: str  # regional_synthesis, cross_domain, player_identity, faction_narrative
    severity: str  # minor, moderate, significant, major, critical

    # Source Layer 2 interpretations that fed this
    source_interpretation_ids: List[str] = field(default_factory=list)

    # Spatial scope
    affected_district_ids: List[str] = field(default_factory=list)
    affected_province_ids: List[str] = field(default_factory=list)

    # Tag-based routing
    affects_tags: List[str] = field(default_factory=list)

    # History tracking
    supersedes_id: Optional[str] = None
    update_count: int = 1

    @staticmethod
    def create(narrative: str, category: str, severity: str,
               source_interpretation_ids: List[str],
               game_time: float, **kwargs) -> ConsolidatedEvent:
        """Factory for creating consolidated events with auto-generated ID."""
        return ConsolidatedEvent(
            consolidation_id=str(uuid.uuid4()),
            created_at=game_time,
            narrative=narrative,
            category=category,
            severity=severity,
            source_interpretation_ids=source_interpretation_ids,
            **kwargs,
        )


@dataclass
class ProvinceSummaryEvent:
    """A province-level summary synthesized from multiple Layer 3 consolidations.

    Layer 4 output. Each province gets one current summary that is superseded
    when new Layer 3 events accumulate. Stored in LayerStore layer4_events +
    layer4_tags.

    Unlike ConsolidatedEvent which has multiple categories (regional, cross-domain,
    etc.), each province produces a single holistic summary. The LLM distills
    all Layer 3 district-level events into a gross summary of provincial state.
    """

    # Identity
    summary_id: str
    province_id: str
    created_at: float  # Game time

    # THE NARRATIVE — core output
    narrative: str  # e.g. "Eastern Highlands: heavy mining, moderate combat, iron scarcity spreading"

    # Classification
    severity: str  # minor, moderate, significant, major, critical

    # Structured fields extracted from LLM output
    dominant_activities: List[str] = field(default_factory=list)  # ["mining", "combat"]
    threat_level: str = "low"  # low, moderate, high, critical

    # Source Layer 3 events that fed this
    source_consolidation_ids: List[str] = field(default_factory=list)

    # Source Layer 2 events included for high-relevance context
    relevant_l2_ids: List[str] = field(default_factory=list)

    # Tag-based routing
    tags: List[str] = field(default_factory=list)

    # History tracking
    supersedes_id: Optional[str] = None

    @staticmethod
    def create(province_id: str, narrative: str, severity: str,
               source_consolidation_ids: List[str],
               game_time: float, **kwargs) -> ProvinceSummaryEvent:
        """Factory with auto-generated summary_id."""
        return ProvinceSummaryEvent(
            summary_id=str(uuid.uuid4()),
            province_id=province_id,
            created_at=game_time,
            narrative=narrative,
            severity=severity,
            source_consolidation_ids=source_consolidation_ids,
            **kwargs,
        )


@dataclass
class RegionSummaryEvent:
    """A region-level summary synthesized from multiple Layer 4 province summaries.

    Layer 5 output. Each game Region produces a single current summary
    that is superseded when new Layer 4 events accumulate enough
    tag-weighted score. Stored in LayerStore layer5_events +
    layer5_tags.

    Aggregation tier: **game Region** (parent of game Province). The
    LLM distills province-level states into a region-scoped narrative
    covering dominant activities, cross-province trends, and overall
    region condition.

    Layer 5 does NOT read from FactionSystem, EcosystemAgent, or any
    other state tracker. It is pure WMS layer pipeline: L4 events +
    L3 events (two-layers-down, tag-filtered) are the only inputs.
    Address tags are FACTS propagated by layer code, never
    synthesized by the LLM. See docs/ARCHITECTURAL_DECISIONS.md for
    rationale.
    """

    # Identity
    summary_id: str
    region_id: str                        # game Region id (e.g. "region_17")
    created_at: float                     # Game time

    # THE NARRATIVE — core output
    narrative: str  # e.g. "Iron Reaches: intensive mining in the
                    # Northern Mines, contested forests to the south"

    # Classification
    severity: str                         # minor, moderate, significant, major, critical

    # Structured fields extracted from LLM output
    dominant_activities: List[str] = field(default_factory=list)  # ["mining", "combat"]
    dominant_provinces: List[str] = field(default_factory=list)   # game province IDs
    region_condition: str = "stable"      # stable, shifting, volatile, crisis

    # Source Layer 4 events that fed this
    source_province_summary_ids: List[str] = field(default_factory=list)

    # Source Layer 3 events included for two-layers-down context
    relevant_l3_ids: List[str] = field(default_factory=list)

    # Tag-based routing
    tags: List[str] = field(default_factory=list)

    # History tracking
    supersedes_id: Optional[str] = None

    @staticmethod
    def create(region_id: str, narrative: str, severity: str,
               source_province_summary_ids: List[str],
               game_time: float, **kwargs) -> RegionSummaryEvent:
        """Factory with auto-generated summary_id."""
        return RegionSummaryEvent(
            summary_id=str(uuid.uuid4()),
            region_id=region_id,
            created_at=game_time,
            narrative=narrative,
            severity=severity,
            source_province_summary_ids=source_province_summary_ids,
            **kwargs,
        )


@dataclass
class NationSummaryEvent:
    """A nation-level summary synthesized from multiple Layer 5 region summaries.

    Layer 6 output. Each game Nation produces a single current summary
    that is superseded when new Layer 5 events accumulate enough
    tag-weighted score. Stored in LayerStore layer6_events +
    layer6_tags.

    Aggregation tier: **game Nation** (parent of game Region). The
    LLM distills region-level states into a nation-scoped narrative
    covering dominant activities, cross-region trends, and overall
    nation condition.

    Layer 6 does NOT read from FactionSystem, EcosystemAgent, or any
    other state tracker. It is pure WMS layer pipeline: L5 events +
    L4 events (two-layers-down, tag-filtered) are the only inputs.
    Address tags are FACTS propagated by layer code, never
    synthesized by the LLM. See docs/ARCHITECTURAL_DECISIONS.md §6.
    """

    # Identity
    summary_id: str
    nation_id: str                        # game Nation id (e.g. "nation_3")
    created_at: float                     # Game time

    # THE NARRATIVE — core output
    narrative: str  # e.g. "Northern Kingdom: Iron Reaches drives heavy
                    # mining, while Emerald Valley sees steady farming"

    # Classification
    severity: str                         # minor, moderate, significant, major, critical

    # Structured fields extracted from LLM output
    dominant_activities: List[str] = field(default_factory=list)  # ["mining", "combat"]
    dominant_regions: List[str] = field(default_factory=list)     # game region IDs
    nation_condition: str = "stable"      # stable, shifting, volatile, crisis

    # Source Layer 5 events that fed this
    source_region_summary_ids: List[str] = field(default_factory=list)

    # Source Layer 4 events included for two-layers-down context
    relevant_l4_ids: List[str] = field(default_factory=list)

    # Tag-based routing
    tags: List[str] = field(default_factory=list)

    # History tracking
    supersedes_id: Optional[str] = None

    @staticmethod
    def create(nation_id: str, narrative: str, severity: str,
               source_region_summary_ids: List[str],
               game_time: float, **kwargs) -> NationSummaryEvent:
        """Factory with auto-generated summary_id."""
        return NationSummaryEvent(
            summary_id=str(uuid.uuid4()),
            nation_id=nation_id,
            created_at=game_time,
            narrative=narrative,
            severity=severity,
            source_region_summary_ids=source_region_summary_ids,
            **kwargs,
        )


@dataclass
class WorldSummaryEvent:
    """A world-level summary synthesized from multiple Layer 6 nation summaries.

    Layer 7 output. The game has exactly one World (``world_0``), so this
    is a singleton-bucket pattern — one current summary that is superseded
    when enough new Layer 6 nation events accumulate. Stored in LayerStore
    layer7_events + layer7_tags.

    Aggregation tier: **game World** (parent of game Nation). The LLM
    distills nation-level states into a world-scoped narrative covering
    dominant activities, dominant nations, cross-nation trends, and
    overall world condition.

    This is the final aggregation tier — no Layer 8 planned. Layer 7
    does NOT read from FactionSystem, EcosystemAgent, or any other state
    tracker. It is pure WMS layer pipeline: L6 events + L5 events
    (two-layers-down, tag-filtered) are the only inputs. Address tags
    are FACTS propagated by layer code, never synthesized by the LLM.
    See docs/ARCHITECTURAL_DECISIONS.md §6.
    """

    # Identity
    summary_id: str
    world_id: str                          # game World id (always "world_0")
    created_at: float                      # Game time

    # THE NARRATIVE — core output
    narrative: str  # e.g. "The Known Lands: the Northern Kingdom drives
                    # intensive mining, while the Southern Empire sees
                    # escalating conflict along its borders"

    # Classification
    severity: str                          # minor, moderate, significant, major, critical

    # Structured fields extracted from LLM output
    dominant_activities: List[str] = field(default_factory=list)   # ["mining", "combat"]
    dominant_nations: List[str] = field(default_factory=list)      # game nation IDs
    world_condition: str = "stable"        # stable, shifting, volatile, crisis

    # Source Layer 6 events that fed this
    source_nation_summary_ids: List[str] = field(default_factory=list)

    # Source Layer 5 events included for two-layers-down context
    relevant_l5_ids: List[str] = field(default_factory=list)

    # Tag-based routing
    tags: List[str] = field(default_factory=list)

    # History tracking
    supersedes_id: Optional[str] = None

    @staticmethod
    def create(world_id: str, narrative: str, severity: str,
               source_nation_summary_ids: List[str],
               game_time: float, **kwargs) -> "WorldSummaryEvent":
        """Factory with auto-generated summary_id."""
        return WorldSummaryEvent(
            summary_id=str(uuid.uuid4()),
            world_id=world_id,
            created_at=game_time,
            narrative=narrative,
            severity=severity,
            source_nation_summary_ids=source_nation_summary_ids,
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

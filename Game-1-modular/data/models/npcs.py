"""NPC definition data model — v3 schema.

v3 splits NPC data into static (this dataclass + JSON) and dynamic (faction
SQLite tables: npc_dynamic_state, npc_dialogue_log, npc_affinity). Static
fields are immutable for the NPC's lifetime; dynamic state is mutated at
runtime through NPCMemoryManager / FactionSystem.

Static schema rationale:
- narrative is the immutable past, load-bearing for WNS retrieval and
  faction npc_profiles.narrative.
- personality is INLINE per-NPC (no template FK) — gives every NPC a
  unique voice that the LLM agent reads directly.
- locality.home_chunk is the cultural/narrative anchor (where the NPC is
  *from*); position is the runtime spawn (separate concern).
- speechbank holds birth-time canned dialogue + a phrase_bank that pins
  cultural voice tokens into every LLM-generated response.
- affinity_seeds get written to faction's npc_affinity table at NPC birth.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
from .world import Position


@dataclass
class NPCDefinition:
    """NPC v3 — static design data."""

    npc_id: str
    name: str
    title: str = ""

    narrative: str = ""

    personality: Dict[str, Any] = field(default_factory=dict)

    locality: Dict[str, Any] = field(default_factory=dict)

    faction: Dict[str, Any] = field(default_factory=dict)

    affinity_seeds: Dict[str, int] = field(default_factory=dict)

    services: Dict[str, Any] = field(default_factory=dict)
    unlock_conditions: Dict[str, Any] = field(default_factory=dict)

    speechbank: Dict[str, Any] = field(default_factory=dict)

    quests: List[str] = field(default_factory=list)

    position: Position = field(default_factory=lambda: Position(0.0, 0.0, 0.0))
    sprite_color: Tuple[int, int, int] = (200, 200, 200)
    interaction_radius: float = 3.0

    tags: List[str] = field(default_factory=list)

    dialogue_lines: List[str] = field(default_factory=list)

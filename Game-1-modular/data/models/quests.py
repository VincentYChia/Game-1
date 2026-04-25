"""Quest data models — v3 schema.

v3 quest lifecycle:
- Static JSON (this dataclass + quests-3.JSON) is the immutable design template.
- In-progress quests carry only PROSE reward estimates (rewards_prose). The
  legacy concrete `rewards` field stays for hand-authored tutorial quests
  whose numerical rewards are already tuned.
- LLM-generated quests emit prose only. A future reward materializer
  resolves prose -> concrete numbers at quest accept time.
- Archive at turn-in records actual outcomes for WNS narrative continuity
  (NOT in this dataclass — lives in WMS / a future archive table).

Fields preserved from earlier schemas for runtime compatibility:
- quest_id, title, description (string), npc_id, objectives, rewards,
  completion_dialogue.

New v3 fields are additive — runtime code that does not know about them
keeps working.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class QuestObjective:
    """Quest objective.

    objective_type allow-list (v3): gather, combat, kill_target, craft,
    deliver, explore, talk. Runtime currently handles gather + combat;
    other types load as data but are no-ops at completion check until
    wired.

    items[] entry shape varies by type:
      gather:      {item_id, quantity, description?, optional?}
      combat:      (uses enemies_killed scalar; items[] empty)
      kill_target: {target_id, quantity, description?, optional?}
      craft:       {recipe_id, quantity, description?, optional?}
      deliver:     {item_id, quantity, recipient_npc_id, description?}
      explore:     {chunk_id, description?}
      talk:        {npc_id, description?}
    """
    objective_type: str
    items: List[Dict[str, Any]] = field(default_factory=list)
    enemies_killed: int = 0  # combat only; ignored for other types


@dataclass
class QuestRewards:
    """Concrete numerical rewards. Hand-authored tutorial quests use these
    directly. LLM-generated quests use rewards_prose on QuestDefinition
    instead, which a future resolver will materialize into this shape at
    quest accept time.
    """
    experience: int = 0
    gold: int = 0

    health_restore: int = 0
    mana_restore: int = 0

    skills: List[str] = field(default_factory=list)
    items: List[Dict[str, Any]] = field(default_factory=list)
    title: str = ""
    stat_points: int = 0

    status_effects: List[Dict[str, Any]] = field(default_factory=list)
    buffs: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class QuestDefinition:
    """Quest v3 — static design template."""

    quest_id: str
    title: str = ""
    description: str = ""  # legacy — long-form string for runtime UI
    npc_id: str = ""        # legacy — alias for given_by

    objectives: QuestObjective = field(
        default_factory=lambda: QuestObjective(objective_type="gather")
    )
    rewards: QuestRewards = field(default_factory=QuestRewards)

    completion_dialogue: List[str] = field(default_factory=list)

    # ── v3 additions (additive; backward-compatible defaults) ────────

    name: str = ""              # display name (Title Case, alias for title)
    quest_type: str = "side"    # tutorial / side / main / chain / repeatable / hidden
    tier: int = 1
    given_by: str = ""          # NPC who offers (cross-ref) — alias of npc_id
    return_to: str = ""         # NPC to turn in to (defaults to given_by)

    description_full: Dict[str, Any] = field(default_factory=dict)
    # Rich description: {short, long, narrative}. description (str) holds
    # description_full["long"] (or short fallback) for legacy consumers.

    rewards_prose: Dict[str, Any] = field(default_factory=dict)
    # LLM-generated prose hints — populated when rewards.experience/gold
    # are zero and concrete rewards have not been materialized yet.

    requirements: Dict[str, Any] = field(default_factory=dict)
    # {characterLevel, stats, titles, completedQuests, factionAffinity?}

    expiration: Dict[str, Any] = field(default_factory=dict)
    # {type: time_limit_seconds | world_state | npc_death | chunk_destroyed
    #   | none, ...type-specific fields}

    progression: Dict[str, Any] = field(default_factory=dict)
    # {isRepeatable, cooldown, nextQuest, questChain}

    wns_thread_id: str = ""
    # Optional link to a WNS narrative thread (future wiring).

    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # {narrative, difficulty, estimatedTime} — tags promoted to top-level.

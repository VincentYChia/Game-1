"""NPC Database - manages NPCs and quests.

Schema versions:
- v3 (canonical): npcs-3.JSON. Full inline personality, speechbank, locality,
  faction, affinity_seeds. See data/models/npcs.py for shape.
- v2 (legacy fallback): npcs-enhanced.JSON. Adapter fills v3 defaults.
- v1 has been removed.
"""

import json
from pathlib import Path
from typing import Any, Dict, List
from data.models.npcs import NPCDefinition
from data.models.quests import QuestDefinition, QuestObjective, QuestRewards
from data.models.world import Position
from core.paths import get_resource_path


def _flatten_speechbank_to_dialogue_lines(speechbank: Dict[str, Any]) -> List[str]:
    """Build a backwards-compatible dialogue_lines list from a v3 speechbank.

    Existing consumers (npc_system.NPC.get_dialogue) cycle through dialogue_lines
    for the basic non-LLM dialogue UI. We seed it with greeting + idle_barks so
    the legacy cycling behavior produces sensible output without an LLM call.
    """
    lines: List[str] = []
    greeting = speechbank.get("greeting", [])
    if isinstance(greeting, list):
        lines.extend(greeting)
    idle_barks = speechbank.get("idle_barks", [])
    if isinstance(idle_barks, list):
        lines.extend(idle_barks)
    return lines


def _build_npc_from_v3(npc_data: Dict[str, Any]) -> NPCDefinition:
    """Build NPCDefinition from a v3 record (canonical schema)."""
    pos_data = npc_data.get("position", {"x": 0, "y": 0, "z": 0})
    position = Position(pos_data.get("x", 0.0), pos_data.get("y", 0.0), pos_data.get("z", 0.0))

    speechbank = npc_data.get("speechbank", {})
    metadata = npc_data.get("metadata", {})

    return NPCDefinition(
        npc_id=npc_data["npc_id"],
        name=npc_data["name"],
        title=npc_data.get("title", ""),
        narrative=npc_data.get("narrative", ""),
        personality=npc_data.get("personality", {}),
        locality=npc_data.get("locality", {}),
        faction=npc_data.get("faction", {}),
        affinity_seeds=npc_data.get("affinity_seeds", {}),
        services=npc_data.get("services", {}),
        unlock_conditions=npc_data.get("unlockConditions", {}),
        speechbank=speechbank,
        quests=npc_data.get("quests", []),
        position=position,
        sprite_color=tuple(npc_data.get("sprite_color", [200, 200, 200])),
        interaction_radius=float(npc_data.get("interaction_radius", 3.0)),
        tags=metadata.get("tags", []),
        dialogue_lines=_flatten_speechbank_to_dialogue_lines(speechbank),
    )


def _flatten_description(desc: Any) -> str:
    """Coerce description to a string for legacy consumers.

    v3 stores rich description in description_full (dict). The flat string
    fallback prefers 'long' then 'short'.
    """
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict):
        return desc.get("long") or desc.get("short") or ""
    return ""


def _build_quest_objective(obj_data: Dict[str, Any]) -> QuestObjective:
    """Build QuestObjective from JSON. Tolerates 'type' or 'objective_type' keys."""
    obj_type = obj_data.get("objective_type", obj_data.get("type", "gather"))
    return QuestObjective(
        objective_type=obj_type,
        items=obj_data.get("items", []),
        enemies_killed=obj_data.get("enemies_killed", 0),
    )


def _build_quest_rewards(rew_data: Dict[str, Any]) -> QuestRewards:
    """Build QuestRewards from JSON. Tolerates camelCase + snake_case stat key."""
    return QuestRewards(
        experience=rew_data.get("experience", 0),
        gold=rew_data.get("gold", 0),
        health_restore=rew_data.get("health_restore", 0),
        mana_restore=rew_data.get("mana_restore", 0),
        skills=rew_data.get("skills", []),
        items=rew_data.get("items", []),
        title=rew_data.get("title") or "",
        stat_points=rew_data.get("stat_points", rew_data.get("statPoints", 0)),
        status_effects=rew_data.get("status_effects", []),
        buffs=rew_data.get("buffs", []),
    )


def _build_quest_from_v3(quest_data: Dict[str, Any]) -> QuestDefinition:
    """Build QuestDefinition from a v3 record (canonical schema)."""
    quest_id = quest_data["quest_id"]
    title = quest_data.get("title", quest_data.get("name", "Untitled Quest"))
    name = quest_data.get("name", title)

    description_full = quest_data.get("description_full", {})
    description_str = _flatten_description(description_full or quest_data.get("description", ""))

    npc_id = quest_data.get("npc_id", quest_data.get("given_by", ""))
    given_by = quest_data.get("given_by", npc_id)
    return_to = quest_data.get("return_to", given_by)

    metadata = quest_data.get("metadata", {})

    return QuestDefinition(
        quest_id=quest_id,
        title=title,
        description=description_str,
        npc_id=npc_id,
        objectives=_build_quest_objective(quest_data.get("objectives", {})),
        rewards=_build_quest_rewards(quest_data.get("rewards", {})),
        completion_dialogue=quest_data.get("completion_dialogue", []),
        name=name,
        quest_type=quest_data.get("quest_type", "side"),
        tier=int(quest_data.get("tier", 1)),
        given_by=given_by,
        return_to=return_to,
        description_full=description_full if isinstance(description_full, dict) else {},
        rewards_prose=quest_data.get("rewards_prose", {}),
        requirements=quest_data.get("requirements", {}),
        expiration=quest_data.get("expiration", {}),
        progression=quest_data.get("progression", {}),
        wns_thread_id=quest_data.get("wns_thread_id", ""),
        tags=metadata.get("tags", []),
        metadata=metadata,
    )


def _build_quest_from_v2(quest_data: Dict[str, Any]) -> QuestDefinition:
    """Adapter: build QuestDefinition from a v2 (quests-enhanced) record.

    v2 uses camelCase keys (givenBy, questType, returnTo) and lacks
    rewards_prose / wns_thread_id / expiration. We populate v3 fields with
    sensible defaults.
    """
    quest_id = quest_data.get("quest_id", quest_data.get("questId", ""))
    title = quest_data.get("title", quest_data.get("name", "Untitled Quest"))
    name = quest_data.get("name", title)

    description_full = quest_data.get("description", {})
    description_str = _flatten_description(description_full)

    npc_id = quest_data.get("npc_id", quest_data.get("givenBy", ""))
    given_by = quest_data.get("givenBy", npc_id)
    return_to = quest_data.get("returnTo", given_by)

    metadata = quest_data.get("metadata", {})

    return QuestDefinition(
        quest_id=quest_id,
        title=title,
        description=description_str,
        npc_id=npc_id,
        objectives=_build_quest_objective(quest_data.get("objectives", {})),
        rewards=_build_quest_rewards(quest_data.get("rewards", {})),
        completion_dialogue=quest_data.get("completion_dialogue", []),
        name=name,
        quest_type=quest_data.get("questType", "side"),
        tier=int(quest_data.get("tier", 1)),
        given_by=given_by,
        return_to=return_to,
        description_full=description_full if isinstance(description_full, dict) else {},
        rewards_prose={},
        requirements=quest_data.get("requirements", {}),
        expiration={},
        progression=quest_data.get("progression", {}),
        wns_thread_id="",
        tags=metadata.get("tags", []),
        metadata=metadata,
    )


def _build_npc_from_v2(npc_data: Dict[str, Any]) -> NPCDefinition:
    """Adapter: build NPCDefinition from a v2 (npcs-enhanced) record.

    v2 is missing personality, speechbank, locality, faction, affinity_seeds.
    We fill these with empty defaults — runtime systems must tolerate empty
    dicts. dialogue_lines comes from v2's nested dialogue.dialogue_lines or
    greeting fallbacks.
    """
    pos_data = npc_data["position"]
    position = Position(pos_data["x"], pos_data["y"], pos_data["z"])

    dialogue_obj = npc_data.get("dialogue", {})
    dialogue_lines = dialogue_obj.get("dialogue_lines", [])
    if not dialogue_lines:
        greeting = dialogue_obj.get("greeting", {})
        if isinstance(greeting, dict):
            dialogue_lines = [
                greeting.get("default", "Hello!"),
                greeting.get("questInProgress", "How goes your task?"),
                greeting.get("questComplete", "Well done!"),
            ]
        else:
            dialogue_lines = [str(greeting)] if greeting else ["Hello!"]

    behavior = npc_data.get("behavior", {})
    interaction_radius = float(behavior.get("interactionRange", npc_data.get("interaction_radius", 3.0)))

    metadata = npc_data.get("metadata", {})

    return NPCDefinition(
        npc_id=npc_data["npc_id"],
        name=npc_data["name"],
        title=npc_data.get("title", ""),
        narrative=metadata.get("narrative", ""),
        personality={},
        locality={},
        faction={},
        affinity_seeds={},
        services=npc_data.get("services", {}),
        unlock_conditions=npc_data.get("unlockConditions", {}),
        speechbank={},
        quests=npc_data.get("quests", []),
        position=position,
        sprite_color=tuple(npc_data["sprite_color"]),
        interaction_radius=interaction_radius,
        tags=metadata.get("tags", []),
        dialogue_lines=dialogue_lines,
    )


class NPCDatabase:
    """Singleton database of all NPCs"""
    _instance = None

    def __init__(self):
        self.npcs: Dict[str, NPCDefinition] = {}
        self.quests: Dict[str, QuestDefinition] = {}
        self.loaded = False
        self.source_version: str = ""        # which NPC file version was loaded
        self.quest_source_version: str = ""  # which quest file version was loaded

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_from_files(self):
        """Load NPCs and quests from JSON files. Prefers v3 (npcs-3.JSON);
        falls back to v2 (npcs-enhanced.JSON) one cycle for safety. v1 dropped.
        """
        try:
            # NPCs: v3 preferred, v2 fallback. No v1.
            v3_path = get_resource_path("progression/npcs-3.JSON")
            v2_path = get_resource_path("progression/npcs-enhanced.JSON")

            if v3_path.exists():
                with open(v3_path, 'r') as f:
                    data = json.load(f)
                    for npc_data in data.get("npcs", []):
                        npc_def = _build_npc_from_v3(npc_data)
                        self.npcs[npc_def.npc_id] = npc_def
                self.source_version = "v3"
                print(f"[OK] Loaded {len(self.npcs)} NPCs from {v3_path.name} (v3)")
            elif v2_path.exists():
                with open(v2_path, 'r') as f:
                    data = json.load(f)
                    for npc_data in data.get("npcs", []):
                        npc_def = _build_npc_from_v2(npc_data)
                        self.npcs[npc_def.npc_id] = npc_def
                self.source_version = "v2"
                print(f"[OK] Loaded {len(self.npcs)} NPCs from {v2_path.name} (v2 fallback)")
            else:
                print(f"[WARN] No NPC file found (looked for npcs-3.JSON, npcs-enhanced.JSON)")

            # Quests: v3 preferred, v2 fallback. v1 dropped.
            v3_quest_path = get_resource_path("progression/quests-3.JSON")
            v2_quest_path = get_resource_path("progression/quests-enhanced.JSON")

            if v3_quest_path.exists():
                with open(v3_quest_path, 'r') as f:
                    data = json.load(f)
                    for quest_data in data.get("quests", []):
                        quest_def = _build_quest_from_v3(quest_data)
                        self.quests[quest_def.quest_id] = quest_def
                self.quest_source_version = "v3"
                print(f"[OK] Loaded {len(self.quests)} quests from {v3_quest_path.name} (v3)")
            elif v2_quest_path.exists():
                with open(v2_quest_path, 'r') as f:
                    data = json.load(f)
                    for quest_data in data.get("quests", []):
                        quest_def = _build_quest_from_v2(quest_data)
                        self.quests[quest_def.quest_id] = quest_def
                self.quest_source_version = "v2"
                print(f"[OK] Loaded {len(self.quests)} quests from {v2_quest_path.name} (v2 fallback)")
            else:
                print(f"[WARN] No quest file found (looked for quests-3.JSON, quests-enhanced.JSON)")

            self.loaded = True
        except Exception as e:
            print(f"[WARN] Failed to load NPCs/Quests: {e}")
            import traceback
            traceback.print_exc()
            self.loaded = False

    def reload(self) -> None:
        """Re-read NPC + Quest JSON files from disk.

        Called by :func:`world_system.content_registry.database_reloader`
        after the Content Registry commits new ``npcs-generated-*`` or
        ``quests-generated-*`` files. Drops the existing in-memory
        caches and reloads the canonical JSON sources, then merges any
        ``progression/npcs-generated-*.JSON`` / ``progression/quests-
        generated-*.JSON`` siblings on top.

        Idempotent — safe to call multiple times. Never raises; on any
        failure the in-memory state is left as-is (prefer stale-but-
        intact over crashing the game loop).
        """
        old_npcs = dict(self.npcs)
        old_quests = dict(self.quests)
        old_loaded = self.loaded
        try:
            self.npcs = {}
            self.quests = {}
            self.loaded = False
            self.load_from_files()
            self._merge_generated_files()
        except Exception as e:
            print(f"[NPCDatabase] reload failed, keeping previous state: {e}")
            self.npcs = old_npcs
            self.quests = old_quests
            self.loaded = old_loaded

    def _merge_generated_files(self) -> None:
        """Pick up any ``progression/npcs-generated-*.JSON`` or
        ``progression/quests-generated-*.JSON`` siblings produced by
        the Content Registry. Generated entries override duplicate
        IDs in the canonical files (last-writer-wins, so the latest
        WES generation is what the runtime sees).
        """
        try:
            progression_dir = get_resource_path("progression")
        except Exception:
            return
        try:
            for path in sorted(progression_dir.glob("npcs-generated-*.JSON")):
                try:
                    with open(path, "r") as f:
                        data = json.load(f)
                    for npc_data in data.get("npcs", []):
                        try:
                            npc_def = _build_npc_from_v3(npc_data)
                            self.npcs[npc_def.npc_id] = npc_def
                        except Exception as inner:
                            print(f"[NPCDatabase] skipping malformed npc in {path.name}: {inner}")
                except Exception as outer:
                    print(f"[NPCDatabase] failed to merge {path.name}: {outer}")

            for path in sorted(progression_dir.glob("quests-generated-*.JSON")):
                try:
                    with open(path, "r") as f:
                        data = json.load(f)
                    for quest_data in data.get("quests", []):
                        try:
                            quest_def = _build_quest_from_v3(quest_data)
                            # Generated quests opt into the adaptive
                            # reward flow (pre-gen at receive + adapt
                            # at turn-in). Canonical quests from
                            # quests-3.JSON keep source_origin =
                            # "canonical" (the default) and use their
                            # hand-tuned rewards verbatim.
                            quest_def.source_origin = "generated"
                            self.quests[quest_def.quest_id] = quest_def
                        except Exception as inner:
                            print(f"[NPCDatabase] skipping malformed quest in {path.name}: {inner}")
                except Exception as outer:
                    print(f"[NPCDatabase] failed to merge {path.name}: {outer}")
        except Exception as e:
            print(f"[NPCDatabase] _merge_generated_files outer error: {e}")

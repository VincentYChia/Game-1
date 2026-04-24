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
        self.source_version: str = ""  # which file version was actually loaded

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

            # Try loading enhanced quests first, fallback to v1.0
            quest_files = [
                get_resource_path("progression/quests-enhanced.JSON"),
                get_resource_path("progression/quests-1.JSON")
            ]

            for quest_path in quest_files:
                if quest_path.exists():
                    with open(quest_path, 'r') as f:
                        data = json.load(f)
                        for quest_data in data.get("quests", []):
                            # Parse objectives (support both formats)
                            obj_data = quest_data["objectives"]

                            # Support both "type" and "objective_type"
                            obj_type = obj_data.get("type", obj_data.get("objective_type", "gather"))

                            objective = QuestObjective(
                                objective_type=obj_type,
                                items=obj_data.get("items", []),
                                enemies_killed=obj_data.get("enemies_killed", 0)
                            )

                            # Parse rewards (support both formats)
                            rew_data = quest_data["rewards"]
                            rewards = QuestRewards(
                                experience=rew_data.get("experience", 0),
                                gold=rew_data.get("gold", 0),
                                health_restore=rew_data.get("health_restore", 0),
                                mana_restore=rew_data.get("mana_restore", 0),
                                skills=rew_data.get("skills", []),
                                items=rew_data.get("items", []),
                                title=rew_data.get("title", ""),
                                stat_points=rew_data.get("statPoints", rew_data.get("stat_points", 0)),
                                status_effects=rew_data.get("status_effects", []),
                                buffs=rew_data.get("buffs", [])
                            )

                            # Support both "quest_id" and "questId", "title" and "name"
                            quest_id = quest_data.get("quest_id", quest_data.get("questId", ""))
                            title = quest_data.get("title", quest_data.get("name", "Untitled Quest"))

                            # Support both simple and complex description formats
                            description = quest_data.get("description", "")
                            if isinstance(description, dict):
                                description = description.get("long", description.get("short", ""))

                            # Support both "npc_id" and "givenBy"
                            npc_id = quest_data.get("npc_id", quest_data.get("givenBy", ""))

                            quest_def = QuestDefinition(
                                quest_id=quest_id,
                                title=title,
                                description=description,
                                npc_id=npc_id,
                                objectives=objective,
                                rewards=rewards,
                                completion_dialogue=quest_data.get("completion_dialogue", [])
                            )
                            self.quests[quest_def.quest_id] = quest_def
                    print(f"[OK] Loaded {len(self.quests)} quests from {quest_path.name}")
                    break

            self.loaded = True
        except Exception as e:
            print(f"[WARN] Failed to load NPCs/Quests: {e}")
            import traceback
            traceback.print_exc()
            self.loaded = False

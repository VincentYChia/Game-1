"""Realistic sample-input generation for the Prompt Studio simulator.

Each LLM task has a ``sample_input_key`` in the registry. This module
maps that key to a builder function that returns a dict of
``${variable_name}`` substitutions plus, where relevant, an extra-tags
list and a free-form "data block" for WMS-style tag-indexed prompts.

Inputs come from the LIVE game databases when possible
(MaterialDatabase, NPCDatabase, ResourceNodeDatabase, EnemyDatabase) so
"Run with fixture" and "Run with mock" buttons exercise the real cross-
ref allow-lists. The builders degrade gracefully if a database isn't
loaded — they fall back to hand-coded plausible values.

Adding a new task:
1. Pick a ``sample_input_key`` (multiple LLM systems can share one).
2. Add a builder function ``build_<key>() -> SampleInput`` below.
3. Reference it in the SAMPLE_BUILDERS dict at the bottom.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ── Result type ──────────────────────────────────────────────────────────

@dataclass
class SampleInput:
    """One realistic input set for a task.

    - ``variables``: the ``${var}`` substitutions for WES-style templates
      (planner, hub, tool, supervisor, weaver, etc.).
    - ``tags``: a list of WMS-style tags (e.g. ``["species:wolf_grey",
      "action:kill"]``) for tag-indexed assemblers.
    - ``data_block``: free-text "data block" appended to the user prompt
      after the assembled fragments — only used by WMS assemblers.
    - ``label``: short description shown in the UI.
    """
    variables: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    data_block: str = ""
    label: str = "(default)"


# ── Database loaders (lazy + tolerant) ──────────────────────────────────

def _try_load_materials() -> List[Dict[str, Any]]:
    try:
        from data.databases import MaterialDatabase
        from core.paths import get_resource_path
        db = MaterialDatabase.get_instance()
        if not getattr(db, "loaded", False):
            db.load_from_file(
                str(get_resource_path("items.JSON/items-materials-1.JSON"))
            )
        out: List[Dict[str, Any]] = []
        for mid, mdef in (db.materials or {}).items():
            out.append({
                "id": mid,
                "name": getattr(mdef, "name", mid),
                "tier": getattr(mdef, "tier", 1),
                "category": getattr(mdef, "category", "ore"),
            })
        return out
    except Exception:
        return []


def _try_load_enemies() -> List[Dict[str, Any]]:
    try:
        import json as _json
        from core.paths import get_resource_path
        with open(get_resource_path("Definitions.JSON/hostiles-1.JSON")) as f:
            data = _json.load(f)
        return [
            {
                "id": e.get("enemyId", ""),
                "name": e.get("name", ""),
                "tier": e.get("tier", 1),
            }
            for e in data.get("enemies", [])
        ]
    except Exception:
        return []


def _try_load_resource_nodes() -> List[Dict[str, Any]]:
    try:
        from data.databases.resource_node_db import ResourceNodeDatabase
        from core.paths import get_resource_path
        db = ResourceNodeDatabase.get_instance()
        if not getattr(db, "loaded", False):
            db.load_from_file(
                str(get_resource_path("Definitions.JSON/resource-node-1.JSON"))
            )
        return [
            {"id": nid, "tier": getattr(nd, "tier", 1)}
            for nid, nd in (db.nodes or {}).items()
        ]
    except Exception:
        return []


def _try_load_chunk_templates() -> List[Dict[str, Any]]:
    try:
        from data.databases.chunk_template_db import ChunkTemplateDatabase
        db = ChunkTemplateDatabase.get_instance()
        return [
            {
                "id": t.chunk_type,
                "name": t.name,
                "category": t.category,
                "theme": t.theme,
            }
            for t in db.get_all()
        ]
    except Exception:
        return []


def _pick(items: List[Dict[str, Any]], default: Dict[str, Any]) -> Dict[str, Any]:
    return random.choice(items) if items else default


# ── Per-task builders ────────────────────────────────────────────────────

def build_wms_layer2() -> SampleInput:
    """Layer 2 fires per tagged event. Realistic: 'killed wolf_grey at locality:hill'."""
    enemies = _try_load_enemies()
    enemy = _pick(enemies, {"id": "wolf_grey", "name": "Grey Wolf", "tier": 1})
    return SampleInput(
        tags=[
            "domain:combat",
            f"species:{enemy['id']}",
            f"tier:{enemy['tier']}",
            "action:kill",
            "result:first",
        ],
        data_block=(
            f"Trigger: enemy_killed ({enemy['id']}) at locality:hill_outskirts\n"
            f"Count today: 3\n"
            f"All-time: 12\n"
            f"Month average per day: 2.1\n"
            f"Recency: 25% of all-time happened today\n"
            f"vs average: 1.4x"
        ),
        label=f"killed {enemy['name']} at locality:hill_outskirts",
    )


def build_wms_layer3() -> SampleInput:
    """L3+ consolidate L2 narratives at higher scales. Generic."""
    return SampleInput(
        tags=[
            "domain:combat",
            "address:district:north_marches",
            "scope:district",
            "interval:daily",
        ],
        data_block=(
            "Layer 2 narratives at this district (last 24h):\n"
            "  - Grey wolves driven back from outskirts (3 kills, 0 losses)\n"
            "  - Iron-deposit yield up 18% over weekly avg\n"
            "  - Two new player-crafted Steel Maces traded at the market\n"
            "  - Slime population in the quarry stable\n"
        ),
        label="district:north_marches consolidation",
    )


def build_wns_layer() -> SampleInput:
    """WNS NL2-NL7 weavers — share a single sample input."""
    return SampleInput(
        variables={
            "layer": 4,
            "address": "region:ashfall_moors",
            "parent_address": "province:northern_marches",
            "grandparent_address": "nation:kingdom_of_iron",
            "wms_context": (
                "[severity:high] economy: copper trade restructuring "
                "around the moors, three smithies expanded.\n"
                "[severity:moderate] combat: dire-wolf kills steady; "
                "no escalation.\n"
                "[severity:low] gathering: fishing yields up 12% at "
                "tranquil lake."
            ),
            "recent_narrative_threads": (
                "thread:moors_copper_economy (open, 4 mentions)\n"
                "thread:northern_dire_wolves (open, 2 mentions)"
            ),
            "scope_rule": "Discuss only events within this region; do not "
                          "reference adjacent provinces unless their threads "
                          "appear in recent_narrative_threads.",
        },
        label="region:ashfall_moors at NL4",
    )


def build_wes_planner() -> SampleInput:
    return SampleInput(
        variables={
            "bundle_id": "bundle_demo_001",
            "directive": (
                "Generate content responding to the moors' copper trade "
                "restructuring: new faction interests, NPCs drawn to copper "
                "markets, possibly a new node variant."
            ),
            "narrative_brief": (
                "Ashfall Moors are restructuring around copper trade; three "
                "smithies expanded; a new merchant guild forming in the "
                "district."
            ),
            "address": "region:ashfall_moors",
            "firing_tier": 4,
            "rerun_budget": 2,
            "current_content_counts": (
                "hostiles:21, materials:48, nodes:32, skills:107, titles:42, "
                "chunks:21, npcs:8, quests:13"
            ),
        },
        label="bundle for region:ashfall_moors moors copper restructuring",
    )


def build_wes_hub_hostiles() -> SampleInput:
    return SampleInput(
        variables={
            "plan_step_id": "step_3_hostiles",
            "spec_count": 3,
            "tier_floor": 1,
            "tier_ceiling": 3,
            "directive": "Three hostiles thematically tied to copper-rich moors.",
            "address": "region:ashfall_moors",
            "cross_ref_hints": "Material 'moors_copper_seam' may exist in the "
                               "co-emitted plan step; reference if appropriate.",
        },
        label="hub_hostiles: 3 copper-themed enemies in the moors",
    )


def build_wes_hub_materials() -> SampleInput:
    return SampleInput(
        variables={
            "plan_step_id": "step_2_materials",
            "spec_count": 2,
            "tier_floor": 2,
            "tier_ceiling": 3,
            "directive": "Two new copper-related materials at T2-T3.",
            "address": "region:ashfall_moors",
            "cross_ref_hints": "Plan also emits a hostile that drops these.",
        },
        label="hub_materials: 2 copper-related T2-T3 materials",
    )


def build_wes_hub_nodes() -> SampleInput:
    return SampleInput(
        variables={
            "plan_step_id": "step_4_nodes",
            "spec_count": 1,
            "directive": "One new resource node yielding the new copper materials.",
            "address": "region:ashfall_moors",
            "cross_ref_hints": "Yields materials emitted in step_2_materials.",
        },
        label="hub_nodes: 1 moors copper node",
    )


def build_wes_hub_skills() -> SampleInput:
    return SampleInput(
        variables={
            "plan_step_id": "step_5_skills",
            "spec_count": 2,
            "tier_floor": 2,
            "tier_ceiling": 3,
            "directive": "Two skills synergizing with copper-tier weapons.",
            "address": "region:ashfall_moors",
            "cross_ref_hints": "Skills may be granted by titles in step_6.",
        },
        label="hub_skills: 2 copper-tier melee skills",
    )


def build_wes_hub_titles() -> SampleInput:
    return SampleInput(
        variables={
            "plan_step_id": "step_6_titles",
            "spec_count": 2,
            "directive": "Two titles tied to copper trade / smithing.",
            "address": "region:ashfall_moors",
            "cross_ref_hints": "Titles unlock skills from step_5_skills.",
        },
        label="hub_titles: 2 copper-trade titles",
    )


def build_wes_hub_chunks() -> SampleInput:
    return SampleInput(
        variables={
            "plan_step_id": "step_1_chunks",
            "spec_count": 2,
            "directive": "Two new chunk templates: a copper moors variant and a smithy outpost.",
            "address": "region:ashfall_moors",
            "cross_ref_hints": "References resource_id from step_2 / step_4.",
        },
        label="hub_chunks: 2 new biomes for the moors",
    )


def build_wes_hub_npcs() -> SampleInput:
    return SampleInput(
        variables={
            "plan_step_id": "step_7_npcs",
            "spec_count": 2,
            "directive": "Two NPCs: copper merchant + apprentice smith.",
            "address": "district:hill_marches",
            "cross_ref_hints": "Both are anchored to chunks emitted in step_1.",
        },
        label="hub_npcs: copper merchant + apprentice",
    )


def build_wes_hub_quests() -> SampleInput:
    return SampleInput(
        variables={
            "plan_step_id": "step_8_quests",
            "spec_count": 2,
            "directive": "Two quests offered by NPCs from step_7 — gather + kill loop.",
            "address": "district:hill_marches",
            "cross_ref_hints": "Quest objectives reference materials from step_2 and hostiles from step_3.",
        },
        label="hub_quests: copper gather + slime cull",
    )


def build_wes_tool_hostiles() -> SampleInput:
    return SampleInput(
        variables={
            "spec_id": "spec_hostile_001",
            "plan_step_id": "step_3_hostiles",
            "item_intent": "T2 hostile guarding copper deposits in the moors.",
            "hard_constraints": "tier: 2; theme: 'moors'; behavior: territorial.",
            "flavor_hints": "rust-veined hide, hooked spear, harasses solo gatherers.",
            "cross_ref_hints": "drops 'moors_copper_seam' (T2 material)",
        },
        label="tool_hostiles: copperlash_rider (T2 moors guard)",
    )


def build_wes_tool_materials() -> SampleInput:
    return SampleInput(
        variables={
            "spec_id": "spec_material_001",
            "plan_step_id": "step_2_materials",
            "item_intent": "T2 copper variant material from the moors.",
            "hard_constraints": "tier: 2; category: ore; uniqueness: regional.",
            "flavor_hints": "weighty, rust-streaked, smelts cleaner than common copper.",
            "cross_ref_hints": "yielded by node 'moors_copper_seam', dropped by 'copperlash_rider'",
        },
        label="tool_materials: moors_copper_chunk (T2)",
    )


def build_wes_tool_nodes() -> SampleInput:
    return SampleInput(
        variables={
            "spec_id": "spec_node_001",
            "plan_step_id": "step_4_nodes",
            "item_intent": "Resource node yielding moors copper.",
            "hard_constraints": "tier: 2; category: ore.",
            "flavor_hints": "exposed seam, marked by salt-licks; respawns slowly.",
            "cross_ref_hints": "yields 'moors_copper_chunk'",
        },
        label="tool_nodes: moors_copper_seam (T2)",
    )


def build_wes_tool_skills() -> SampleInput:
    return SampleInput(
        variables={
            "spec_id": "spec_skill_001",
            "plan_step_id": "step_5_skills",
            "item_intent": "Active melee skill that scales with copper-tier weapons.",
            "hard_constraints": "tier: 2; mana_cost: moderate; cooldown: short.",
            "flavor_hints": "strike with weight; minor stun on heavy hit; copper resonance.",
            "cross_ref_hints": "granted by title 'Copper Hammer'",
        },
        label="tool_skills: Copper Slam (T2 melee)",
    )


def build_wes_tool_titles() -> SampleInput:
    return SampleInput(
        variables={
            "spec_id": "spec_title_001",
            "plan_step_id": "step_6_titles",
            "item_intent": "Title for proficient copper-trade smiths.",
            "hard_constraints": "tier: 2; unlock: craft 50 copper-tier smithing items.",
            "flavor_hints": "guild-worn name; respected by merchants.",
            "cross_ref_hints": "unlocks skill 'copper_slam'",
        },
        label="tool_titles: Copper Hammer (T2 smithing)",
    )


def build_wes_tool_chunks() -> SampleInput:
    return SampleInput(
        variables={
            "spec_id": "spec_chunk_001",
            "plan_step_id": "step_1_chunks",
            "item_intent": "New chunk template: copper-rich windswept moors.",
            "hard_constraints": "category: dangerous; theme: quarry; tier: T2 dominant.",
            "flavor_hints": "rust-veined cliffs over boggy flats; hostile copper raiders.",
            "cross_ref_hints": "references 'moors_copper_seam' (node) and 'copperlash_rider' (hostile).",
        },
        label="tool_chunks: dangerous_copper_moors",
    )


def build_wes_tool_npcs() -> SampleInput:
    return SampleInput(
        variables={
            "spec_id": "spec_npc_001",
            "plan_step_id": "step_7_npcs",
            "item_intent": "Apprentice smith NPC anchored to the moors smithy chunk.",
            "hard_constraints": "tier:1; faction: traders_guild; locality: district:hill_marches.",
            "flavor_hints": "young, soot-streaked, evasive when asked about elder smiths.",
            "cross_ref_hints": "homes_at chunk 'smithy_outpost'; offers quest 'apprentice_first_haul'.",
        },
        label="tool_npcs: apprentice_smith_thren (apprentice in moors smithy)",
    )


def build_wes_tool_quests() -> SampleInput:
    quests = [
        ("Gather 12 moors_copper_chunk and return to the apprentice smith.", "gather"),
        ("Cull 5 copperlash_rider in the moors quarry.", "kill"),
    ]
    line, kind = random.choice(quests)
    return SampleInput(
        variables={
            "spec_id": f"spec_quest_001_{kind}",
            "plan_step_id": "step_8_quests",
            "item_intent": line,
            "hard_constraints": (
                "tier:1; given_by: 'apprentice_smith_thren'; "
                "expiration: '5 in-game days'."
            ),
            "flavor_hints": "first job for a new apprentice; modest rewards.",
            "cross_ref_hints": (
                "objective references material 'moors_copper_chunk' OR hostile 'copperlash_rider'."
            ),
        },
        label=f"tool_quests: {kind} quest from apprentice",
    )


def build_wes_supervisor() -> SampleInput:
    return SampleInput(
        variables={
            "plan_id": "plan_demo_001",
            "tier_summaries": (
                "Planner: 8 steps planned, no abandons.\n"
                "Hub steps: chunks(2), materials(2), nodes(1), hostiles(3), "
                "skills(2), titles(2), npcs(2), quests(2). All emitted "
                "matching spec_count.\n"
                "Tools: 16 total emits, 0 parse failures, 1 retry on tool_titles.\n"
                "Cross-ref check: 2 unresolved refs (apprentice_first_haul → "
                "missing reward title)."
            ),
            "rerun_budget": 1,
            "directive": "Adjudicate: commit, rerun-with-warning, or rollback?",
        },
        label="supervisor reviewing the demo plan",
    )


def build_wes_quest_reward() -> SampleInput:
    return SampleInput(
        variables={
            "quest_id": "apprentice_first_haul",
            "quest_title": "Apprentice's First Haul",
            "quest_objective": "Gather 12 moors_copper_chunk.",
            "rewards_prose": "modest gold, small XP, a copper-themed minor title.",
            "player_level": 5,
            "tier_floor": 1,
            "tier_ceiling": 2,
            "time_taken_seconds": 1850,
            "expiration_profile": "5 in-game days",
        },
        label="apprentice_first_haul reward materialization",
    )


def build_npc_dialogue() -> SampleInput:
    return SampleInput(
        variables={
            "npc_id": "apprentice_smith_thren",
            "npc_name": "Thren the Apprentice",
            "npc_personality": "earnest, shy, self-deprecating",
            "speechbank_idle": "Mind the heat. Master Vael says I'm not quick enough yet.",
            "player_affinity": 25,
            "faction_affinity": 10,
            "quest_state": "apprentice_first_haul: in_progress",
            "scene_context": "smithy interior, dusk, anvil ringing.",
            "tone_hint": "warm but uncertain.",
        },
        label="dialogue with apprentice_smith_thren during quest",
    )


# ── Dispatch table ───────────────────────────────────────────────────────

SAMPLE_BUILDERS: Dict[str, Callable[[], SampleInput]] = {
    "wms_layer2": build_wms_layer2,
    "wms_layer3": build_wms_layer3,
    "wns_layer": build_wns_layer,
    "wes_planner": build_wes_planner,
    "wes_hub_hostiles": build_wes_hub_hostiles,
    "wes_hub_materials": build_wes_hub_materials,
    "wes_hub_nodes": build_wes_hub_nodes,
    "wes_hub_skills": build_wes_hub_skills,
    "wes_hub_titles": build_wes_hub_titles,
    "wes_hub_chunks": build_wes_hub_chunks,
    "wes_hub_npcs": build_wes_hub_npcs,
    "wes_hub_quests": build_wes_hub_quests,
    "wes_tool_hostiles": build_wes_tool_hostiles,
    "wes_tool_materials": build_wes_tool_materials,
    "wes_tool_nodes": build_wes_tool_nodes,
    "wes_tool_skills": build_wes_tool_skills,
    "wes_tool_titles": build_wes_tool_titles,
    "wes_tool_chunks": build_wes_tool_chunks,
    "wes_tool_npcs": build_wes_tool_npcs,
    "wes_tool_quests": build_wes_tool_quests,
    "wes_supervisor": build_wes_supervisor,
    "wes_quest_reward": build_wes_quest_reward,
    "npc_dialogue": build_npc_dialogue,
}


def build_sample(key: Optional[str]) -> SampleInput:
    """Return a SampleInput for the given key. None / unknown → empty."""
    if key is None:
        return SampleInput()
    builder = SAMPLE_BUILDERS.get(key)
    if builder is None:
        return SampleInput()
    try:
        return builder()
    except Exception as e:
        # Never crash the UI on an input-builder failure.
        return SampleInput(label=f"(builder failed: {type(e).__name__})")


__all__ = ["SampleInput", "SAMPLE_BUILDERS", "build_sample"]

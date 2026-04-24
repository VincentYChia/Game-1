"""Per-tool cross-reference extraction rules.

§7.2 of the working doc commits to a unified ``content_xref`` table
with ``(src_type, src_id, ref_type, ref_id, relationship)`` rows. This
module turns a tool's generated JSON into the list of rows that should
land in that table.

The relationship vocabulary is a **placeholder** per PLACEHOLDER_LEDGER
§10 / §17 — it grows as tool mini-stacks discover what they need. The
starting set:

- ``drops``      — hostile drops a material
- ``uses_skill`` — hostile uses a skill (or skill referenced by another)
- ``yields``     — node yields a material
- ``unlocks``    — title unlocks a skill
- ``bonus_tag``  — title grants a tag bonus

TODO(placeholder — PLACEHOLDER_LEDGER §10): extend relationships as
additional tool mini-stacks ship (hub_skills, hub_hostiles, etc.).

Every extractor is intentionally defensive: unknown fields are
skipped, not errored. This is so tool output shape drift during
design iteration does not break the registry. The **schema validator**
(external to this module — hub/executor_tool concern) is responsible
for rejecting malformed outputs; this module only harvests what it
can see.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


# A single xref tuple: (src_type, src_id, ref_type, ref_id, relationship).
XrefTuple = Tuple[str, str, str, str, str]


# Canonical tool names — singular lowercase, matching the
# ``reg_<tool>`` table names in registry_store (reg_hostiles uses
# ``hostile`` singular for src_type rows to disambiguate from the
# table name; we keep the conventions identical to §7.2 by using
# the plural tool name everywhere).
TOOL_HOSTILES = "hostiles"
TOOL_MATERIALS = "materials"
TOOL_NODES = "nodes"
TOOL_SKILLS = "skills"
TOOL_TITLES = "titles"
TOOL_CHUNKS = "chunks"
TOOL_NPCS = "npcs"

VALID_TOOLS = frozenset(
    {
        TOOL_HOSTILES, TOOL_MATERIALS, TOOL_NODES, TOOL_SKILLS, TOOL_TITLES,
        TOOL_CHUNKS, TOOL_NPCS,
    }
)

# Relationship strings — placeholder vocabulary (§10 / §17 in ledger).
REL_DROPS = "drops"
REL_USES_SKILL = "uses_skill"
REL_YIELDS = "yields"
REL_UNLOCKS = "unlocks"
REL_BONUS_TAG = "bonus_tag"
REL_SPAWNS = "spawns"          # chunk -> resource node / hostile (template)
REL_HOMES_AT = "homes_at"      # npc -> chunk (cultural anchor)
REL_TEACHES = "teaches"        # npc -> skill
REL_REACTS_TO = "reacts_to"    # npc -> material/hostile/skill (event triggers)


def _get_content_id(content_json: Dict[str, Any], tool_name: str) -> str:
    """Extract the primary ID field for a given tool's JSON.

    The existing sacred JSONs use different key names per tool
    (``materialId`` vs. ``enemyId`` vs. ``skillId`` ...). We consult
    all likely shapes and take the first non-empty hit, falling back
    to ``content_id`` for tools that already self-label.
    """
    candidates: List[str] = [
        "content_id",
        "id",
    ]
    # Per-tool: accept both camelCase (sacred JSON files) AND snake_case
    # (v4 generator outputs / fixtures). Order is camelCase first so
    # sacred-file wins when both exist (defensive — they shouldn't both
    # exist on the same payload).
    if tool_name == TOOL_MATERIALS:
        candidates.extend(["materialId", "itemId", "material_id", "item_id"])
    elif tool_name == TOOL_HOSTILES:
        candidates.extend([
            "enemyId", "hostileId", "monsterId",
            "enemy_id", "hostile_id", "monster_id",
        ])
    elif tool_name == TOOL_NODES:
        candidates.extend([
            "nodeId", "resourceNodeId",
            "node_id", "resource_node_id",
        ])
    elif tool_name == TOOL_SKILLS:
        candidates.extend(["skillId", "skill_id"])
    elif tool_name == TOOL_TITLES:
        candidates.extend(["titleId", "title_id"])
    elif tool_name == TOOL_CHUNKS:
        candidates.extend(["chunkType", "chunk_type", "chunkTypeId"])
    elif tool_name == TOOL_NPCS:
        candidates.extend(["npc_id", "npcId"])

    for key in candidates:
        value = content_json.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _get_display_name(content_json: Dict[str, Any]) -> str:
    for key in ("name", "displayName", "display_name", "title"):
        value = content_json.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _get_tier(content_json: Dict[str, Any]) -> int:
    for key in ("tier", "Tier"):
        value = content_json.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0


def _get_biome(content_json: Dict[str, Any]) -> str:
    for key in ("biome", "biomeType", "biome_type"):
        value = content_json.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _get_faction_id(content_json: Dict[str, Any]) -> str:
    for key in ("faction_id", "factionId", "faction"):
        value = content_json.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def extract_header_fields(
    content_json: Dict[str, Any], tool_name: str
) -> Dict[str, Any]:
    """Pull the header columns stored on the ``reg_<tool>`` row.

    Returns a dict with keys: ``content_id, display_name, tier,
    biome, faction_id``. Missing fields are returned as empty
    strings / 0 rather than None to keep SQL writes boring.
    """
    return {
        "content_id": _get_content_id(content_json, tool_name),
        "display_name": _get_display_name(content_json),
        "tier": _get_tier(content_json),
        "biome": _get_biome(content_json),
        "faction_id": _get_faction_id(content_json),
    }


# ── Per-tool xref extractors ─────────────────────────────────────────


def _extract_hostile_xrefs(
    src_id: str, content_json: Dict[str, Any]
) -> List[XrefTuple]:
    out: List[XrefTuple] = []

    # Drops → materials. Shape options encountered in sacred files:
    #   "drops": [{"material_id": "...", "qty": [1,3]}, ...]
    #   "drops": [{"materialId": "..."}]
    #   "drops": ["iron_ore", "copper_ore"]  (tolerated shorthand)
    for drop in content_json.get("drops", []) or []:
        if isinstance(drop, dict):
            mid = drop.get("material_id") or drop.get("materialId")
            if isinstance(mid, str) and mid:
                out.append(
                    (TOOL_HOSTILES, src_id, TOOL_MATERIALS, mid, REL_DROPS)
                )
        elif isinstance(drop, str) and drop:
            out.append(
                (TOOL_HOSTILES, src_id, TOOL_MATERIALS, drop, REL_DROPS)
            )

    # Uses skills. Shape options:
    #   "skills": ["fireball", "bite"]
    #   "skills": [{"skillId": "..."}]
    #   "abilities": [...] (hostiles-1.JSON uses abilities[]; abilities
    #       are defined inline per file, not cross-refs)
    for skill in content_json.get("skills", []) or []:
        if isinstance(skill, dict):
            sid = skill.get("skillId") or skill.get("skill_id") or skill.get("id")
            if isinstance(sid, str) and sid:
                out.append(
                    (TOOL_HOSTILES, src_id, TOOL_SKILLS, sid, REL_USES_SKILL)
                )
        elif isinstance(skill, str) and skill:
            out.append(
                (TOOL_HOSTILES, src_id, TOOL_SKILLS, skill, REL_USES_SKILL)
            )

    return out


def _extract_material_xrefs(
    src_id: str, content_json: Dict[str, Any]
) -> List[XrefTuple]:
    # Materials are leaf content — they don't normally reference
    # other generated content. Future: ``derived_from`` for alloys,
    # but that's not a v4 scope item.
    return []


def _extract_node_xrefs(
    src_id: str, content_json: Dict[str, Any]
) -> List[XrefTuple]:
    out: List[XrefTuple] = []

    # Nodes → materials they yield. Shapes:
    #   "material_id": "iron_ore"
    #   "materialId": "iron_ore"
    #   "yields": [{"material_id": "..."}]
    #   "yields": ["iron_ore"]
    primary = content_json.get("material_id") or content_json.get("materialId")
    if isinstance(primary, str) and primary:
        out.append((TOOL_NODES, src_id, TOOL_MATERIALS, primary, REL_YIELDS))

    for y in content_json.get("yields", []) or []:
        if isinstance(y, dict):
            mid = y.get("material_id") or y.get("materialId")
            if isinstance(mid, str) and mid:
                out.append(
                    (TOOL_NODES, src_id, TOOL_MATERIALS, mid, REL_YIELDS)
                )
        elif isinstance(y, str) and y:
            out.append((TOOL_NODES, src_id, TOOL_MATERIALS, y, REL_YIELDS))

    return out


def _extract_skill_xrefs(
    src_id: str, content_json: Dict[str, Any]
) -> List[XrefTuple]:
    # Skills reference tags (NOT in the registry — sacred vocabulary)
    # and optionally other skills via evolution chains. Evolution
    # chains are NOT in scope (§5 "Designed But NOT Implemented")
    # so we emit no xrefs by default. Future hooks can be added
    # here without schema change.
    return []


def _extract_title_xrefs(
    src_id: str, content_json: Dict[str, Any]
) -> List[XrefTuple]:
    out: List[XrefTuple] = []

    # Titles → skills they unlock.
    for skill in content_json.get("unlocks_skills", []) or []:
        if isinstance(skill, str) and skill:
            out.append(
                (TOOL_TITLES, src_id, TOOL_SKILLS, skill, REL_UNLOCKS)
            )
        elif isinstance(skill, dict):
            sid = skill.get("skillId") or skill.get("skill_id")
            if isinstance(sid, str) and sid:
                out.append(
                    (TOOL_TITLES, src_id, TOOL_SKILLS, sid, REL_UNLOCKS)
                )

    # Titles → bonus tags. Tags are NOT registry rows (sacred vocab
    # per CLAUDE.md), so we do NOT emit xrefs for them. Tag existence
    # checks live outside the registry. Recording them here would
    # produce false-positive orphans.
    # If the designer decides to lift tags into the registry later,
    # the relationship constant ``REL_BONUS_TAG`` is ready to be used.

    return out


def _extract_chunk_xrefs(
    src_id: str, content_json: Dict[str, Any]
) -> List[XrefTuple]:
    """Chunks reference resource-node templates and hostile templates that
    spawn within them. resourceDensity keys are nodeIds (resource node
    templates), enemySpawns keys are enemyIds.
    """
    out: List[XrefTuple] = []

    res_density = content_json.get("resourceDensity") or content_json.get("resource_density") or {}
    if isinstance(res_density, dict):
        for node_id in res_density.keys():
            if isinstance(node_id, str) and node_id:
                out.append(
                    (TOOL_CHUNKS, src_id, TOOL_NODES, node_id, REL_SPAWNS)
                )

    enemy_spawns = content_json.get("enemySpawns") or content_json.get("enemy_spawns") or {}
    if isinstance(enemy_spawns, dict):
        for enemy_id in enemy_spawns.keys():
            if isinstance(enemy_id, str) and enemy_id:
                out.append(
                    (TOOL_CHUNKS, src_id, TOOL_HOSTILES, enemy_id, REL_SPAWNS)
                )

    return out


def _extract_npc_xrefs(
    src_id: str, content_json: Dict[str, Any]
) -> List[XrefTuple]:
    """NPCs reference: home_chunk (locality), teachableSkills (services),
    and event-trigger matches (personality.reaction_modifiers.*).

    Faction tags are NOT registry rows (emergent vocabulary, not validated).
    Quest references are skipped until TOOL_QUESTS is wired.
    Wildcard resource_match entries (e.g. 'herb_*') are skipped — they don't
    resolve to a single id.
    """
    out: List[XrefTuple] = []

    locality = content_json.get("locality") or {}
    home_chunk = locality.get("home_chunk") if isinstance(locality, dict) else None
    if isinstance(home_chunk, str) and home_chunk:
        out.append(
            (TOOL_NPCS, src_id, TOOL_CHUNKS, home_chunk, REL_HOMES_AT)
        )

    services = content_json.get("services") or {}
    if isinstance(services, dict):
        for skill_id in services.get("teachableSkills") or []:
            if isinstance(skill_id, str) and skill_id:
                out.append(
                    (TOOL_NPCS, src_id, TOOL_SKILLS, skill_id, REL_TEACHES)
                )

    personality = content_json.get("personality") or {}
    reaction_modifiers = personality.get("reaction_modifiers") or {} if isinstance(personality, dict) else {}
    if isinstance(reaction_modifiers, dict):
        for _event_type, modifier in reaction_modifiers.items():
            if not isinstance(modifier, dict):
                continue
            for mat_id in modifier.get("resource_match") or []:
                if isinstance(mat_id, str) and mat_id and "*" not in mat_id:
                    out.append(
                        (TOOL_NPCS, src_id, TOOL_MATERIALS, mat_id, REL_REACTS_TO)
                    )
            for enemy_id in modifier.get("enemy_match") or []:
                if isinstance(enemy_id, str) and enemy_id and "*" not in enemy_id:
                    out.append(
                        (TOOL_NPCS, src_id, TOOL_HOSTILES, enemy_id, REL_REACTS_TO)
                    )
            for skill_id in modifier.get("skill_match") or []:
                if isinstance(skill_id, str) and skill_id and "*" not in skill_id:
                    out.append(
                        (TOOL_NPCS, src_id, TOOL_SKILLS, skill_id, REL_REACTS_TO)
                    )

    return out


# Lookup table. Each extractor takes (src_id, content_json) and returns
# a list of xref tuples (src_type included).
_EXTRACTORS = {
    TOOL_HOSTILES: _extract_hostile_xrefs,
    TOOL_MATERIALS: _extract_material_xrefs,
    TOOL_NODES: _extract_node_xrefs,
    TOOL_SKILLS: _extract_skill_xrefs,
    TOOL_TITLES: _extract_title_xrefs,
    TOOL_CHUNKS: _extract_chunk_xrefs,
    TOOL_NPCS: _extract_npc_xrefs,
}


def extract_xrefs(
    tool_name: str, content_json: Dict[str, Any]
) -> List[XrefTuple]:
    """Extract all cross-references implied by a generated JSON blob.

    Returns a list of ``(src_type, src_id, ref_type, ref_id,
    relationship)`` tuples. Empty list if the tool is unknown or the
    content has no cross-refs.

    This is intentionally tolerant — malformed JSONs produce fewer
    xrefs rather than errors. Schema validation is upstream.
    """
    if tool_name not in VALID_TOOLS:
        return []

    src_id = _get_content_id(content_json, tool_name)
    if not src_id:
        return []

    return list(_EXTRACTORS[tool_name](src_id, content_json))


# ── Generated-file JSON shape ────────────────────────────────────────
#
# PLACEHOLDER_LEDGER §17 commits the generated-file paths and to a
# shape that MATCHES the existing sacred file shape for that tool.
# These mappings give the file writer the top-level key each tool
# uses in its sacred file so we can wrap an array of payloads
# correctly.

SACRED_TOP_LEVEL_KEY = {
    TOOL_HOSTILES: "enemies",      # Definitions.JSON/hostiles-1.JSON uses
                                    # "abilities" and "enemies" sections;
                                    # generated hostiles go under
                                    # "enemies".
    TOOL_MATERIALS: "materials",   # items-materials-1.JSON uses
                                    # "materials".
    TOOL_NODES: "resourceNodes",   # resource-node-1.JSON uses
                                    # "resourceNodes" (placeholder — see
                                    # PLACEHOLDER_LEDGER §17).
    TOOL_SKILLS: "skills",         # Skills/skills-skills-1.JSON uses
                                    # "skills".
    TOOL_TITLES: "titles",         # progression/titles-1.JSON uses
                                    # "titles".
    TOOL_CHUNKS: "chunkTemplates", # Chunk-templates-2.JSON uses
                                    # "chunkTemplates".
    TOOL_NPCS: "npcs",             # progression/npcs-3.JSON uses
                                    # "npcs".
}


# Generated JSON output subdirectories. Paths are relative to the game
# module root (``Game-1-modular/``). Per PLACEHOLDER_LEDGER §17 these
# are committed but naming can still be tuned by the designer.
SACRED_OUTPUT_SUBDIR = {
    TOOL_HOSTILES: "Definitions.JSON",
    TOOL_MATERIALS: "items.JSON",
    TOOL_NODES: "Definitions.JSON",
    TOOL_SKILLS: "Skills",
    TOOL_TITLES: "progression",
    TOOL_CHUNKS: "world_system/config",
    TOOL_NPCS: "progression",
}


# Generated-file base names (without timestamp + extension). We append
# ``-generated-<ts>.JSON`` in the file writer.
SACRED_OUTPUT_PREFIX = {
    TOOL_HOSTILES: "hostiles",
    TOOL_MATERIALS: "items-materials",
    TOOL_NODES: "Resource-node",
    TOOL_SKILLS: "skills",
    TOOL_TITLES: "titles",
    TOOL_CHUNKS: "chunk-templates",
    TOOL_NPCS: "npcs",
}

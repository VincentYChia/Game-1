"""Built-in LLM fixtures (v4 P0 — CC4).

Registers the canonical mock I/O pair for every LLM role defined in the v4
System Architecture (§2.7 LLM Roster of ``WORLD_SYSTEM_WORKING_DOC.md``).

This file is imported for its side effects — importing ``llm_fixtures``
triggers ``register()`` for each fixture below.

When a new LLM role is added to the system (e.g. a new tool, a second
supervisor variant), add its fixture here. Each response is a minimal
valid representative, not an exhaustive example.
"""

from __future__ import annotations

from .registry import (
    LLMFixture,
    TIER_NPC,
    TIER_WES,
    TIER_WMS,
    TIER_WNS,
    get_fixture_registry,
)


# ── WMS (for test parity — WMS is already shipped) ────────────────────

_WMS_FIXTURES = [
    LLMFixture(
        code="wms_layer3",
        tier=TIER_WMS,
        description=(
            "WMS L3 district consolidator. Reads L2 narrations in a district, "
            "produces a district-level narration."
        ),
        canonical_system_prompt=(
            "You are a world-memory system consolidator. Given L2 event "
            "narrations in district 'tarmouth', produce a single L3 "
            "consolidation narrating the district's recent state."
        ),
        canonical_user_prompt=(
            "Recent L2 events in district:tarmouth:\n"
            "- A mining party struck copper at the eastern cliffs.\n"
            "- A bandit skirmish left two dead on the north road.\n"
            "- The smith's forge ran hot for three days straight."
        ),
        canonical_response=(
            '{"narrative": "Tarmouth district is uncharacteristically active — '
            'copper is flowing from the cliffs, the forge runs hot, and bandit '
            'pressure on the north road pushed skirmishes to lethality.", '
            '"tags": ["mining", "combat", "smithing", "active_domain", "address:district:tarmouth"]}'
        ),
    ),
    LLMFixture(
        code="wms_layer4",
        tier=TIER_WMS,
        description=(
            "WMS L4 region consolidator. Reads L3 district summaries in a region."
        ),
        canonical_system_prompt=(
            "You are a world-memory system consolidator. Given L3 district "
            "summaries in region 'ashfall_moors', produce a regional narration."
        ),
        canonical_user_prompt=(
            "L3 summaries across ashfall_moors:\n"
            "- tarmouth: mining active, bandit pressure rising\n"
            "- greyfen: quiet; woodcutting only\n"
            "- cindarrow: smithing output at decade high"
        ),
        canonical_response=(
            '{"narrative": "Ashfall Moors is industrially reshaping — smithing '
            'peaks in cindarrow, copper from tarmouth feeds the forges, and the '
            'north road grows dangerous.", '
            '"tags": ["industry", "trade", "banditry", "address:region:ashfall_moors"]}'
        ),
    ),
    LLMFixture(
        code="wms_layer5",
        tier=TIER_WMS,
        description="WMS L5 nation summarizer.",
        canonical_system_prompt=(
            "Summarize national trends from regional L4 summaries."
        ),
        canonical_user_prompt=(
            "Regional summaries in nation:valdren:\n"
            "- ashfall_moors: industrial acceleration, bandit risk\n"
            "- silvervale: steady\n"
            "- thornmere: crop failure second year"
        ),
        canonical_response=(
            '{"narrative": "Valdren strains: industrial surge in the moors contrasts '
            'with thornmere famine pressure. Internal migration likely.", '
            '"tags": ["economic_stress", "famine", "industry", "address:nation:valdren"]}'
        ),
    ),
    LLMFixture(
        code="wms_layer6",
        tier=TIER_WMS,
        description="WMS L6 nation-to-world seam summarizer.",
        canonical_system_prompt=(
            "Summarize cross-national interactions from L5 summaries."
        ),
        canonical_user_prompt=(
            "Nations with significant state this tick:\n"
            "- valdren: industrial surge + famine pressure\n"
            "- khoros: neutral"
        ),
        canonical_response=(
            '{"narrative": "Valdren\'s split fortunes dominate the world stage; '
            'khoros remains dormant.", '
            '"tags": ["valdren_focus", "quiet_world", "address:world:world_0"]}'
        ),
    ),
    LLMFixture(
        code="wms_layer7",
        tier=TIER_WMS,
        description=(
            "WMS L7 world summarizer. Canonical shipped API; listed here for "
            "parity, not because WMS L7 currently consumes fixtures."
        ),
        canonical_system_prompt="Summarize the world's current state.",
        canonical_user_prompt="Top-level L6 summary: Valdren surge + famine.",
        canonical_response=(
            '{"narrative": "The world holds its breath as Valdren reshapes itself.", '
            '"world_condition": "shifting", '
            '"severity": "significant", '
            '"dominant_activities": ["industry", "famine"], '
            '"dominant_nations": ["valdren"]}'
        ),
    ),
]


# ── WNS (v4 new) ──────────────────────────────────────────────────────

_WNS_FIXTURES = [
    LLMFixture(
        code="wns_layer2",
        tier=TIER_WNS,
        description=(
            "WNS NL2 locality weaver. Reads NL1 dialogue mentions and same-locality "
            "WMS L2 narrations; produces thread fragments + local narrative."
        ),
        canonical_system_prompt=(
            "You are the narrative weaver at locality scale. Given recent NPC "
            "dialogue mentions and WMS event narrations at this locality, identify "
            "narrative threads that exist or are extending. Output JSON with threads."
        ),
        canonical_user_prompt=(
            "Locality: locality:tarmouth_copperdocks\n"
            "NL1 dialogue mentions:\n"
            "- 'bandits are getting bold' (x3 NPCs)\n"
            "- 'copper prices doubled overnight'\n"
            "WMS L2 same-locality events:\n"
            "- bandit_skirmish (moderate severity, x2 this week)\n"
            "- mining_strike_copper (major)"
        ),
        canonical_response=(
            '{"narrative": "The copperdocks buzz with prosperity and dread in equal '
            'measure — a strike that lifts the tide and raiders who want a share.", '
            '"threads": [{"headline": "Copper rush draws bandits", '
            '"content_tags": ["prosperity", "banditry", "rising_action"], '
            '"relationship": "open", "parent_thread_id": null}], '
            '"call_wes": false}'
        ),
        notes="call_wes: false — weaver judges the pattern below execution threshold.",
    ),
    LLMFixture(
        code="wns_layer3",
        tier=TIER_WNS,
        description="WNS NL3 district weaver. Reads NL2 threads + WMS L3 at district.",
        canonical_system_prompt=(
            "You are the narrative weaver at district scale. Reconcile with "
            "lower-layer narrative in this district before writing higher-level arcs."
        ),
        canonical_user_prompt=(
            "District: district:tarmouth\n"
            "NL2 threads in district:\n"
            "- 'Copper rush draws bandits' (locality:copperdocks)\n"
            "- 'Smith apprentices abandon the forge' (locality:ironrow)\n"
            "WMS L3: mining active, bandit pressure rising."
        ),
        canonical_response=(
            '{"narrative": "Tarmouth splits: the coast booms on copper while the '
            'forge district loses hands to easier coin.", '
            '"threads": [{"headline": "Labor drain from ironrow", '
            '"content_tags": ["economic_shift", "labor"], '
            '"relationship": "open", "parent_thread_id": null}], '
            '"call_wes": false}'
        ),
    ),
    LLMFixture(
        code="wns_layer4",
        tier=TIER_WNS,
        description="WNS NL4 region weaver.",
        canonical_system_prompt="Weave regional arcs; reconcile with district-level.",
        canonical_user_prompt=(
            "Region: region:ashfall_moors\n"
            "NL3 threads: labor drain from ironrow; unrest on north road."
        ),
        canonical_response=(
            '{"narrative": "The moors are restructuring around the copper trade; old '
            'guild centers weaken.", '
            '"threads": [{"headline": "Smithing guild decline", '
            '"content_tags": ["institutional_decline", "economic_shift"], '
            '"relationship": "open", "parent_thread_id": null}], '
            '"call_wes": true, '
            '"directive_hint": "Generate content responding to the moors\' economic '
            'realignment: new faction interests, new NPCs drawn to copper trade."}'
        ),
        notes="Example of call_wes: true. Weaver judges the pattern warrants execution.",
    ),
    LLMFixture(
        code="wns_layer5",
        tier=TIER_WNS,
        description="WNS NL5 nation weaver.",
        canonical_system_prompt="Weave national arcs.",
        canonical_user_prompt=(
            "Nation: nation:valdren\n"
            "NL4 regional narratives: ashfall moors restructuring; thornmere famine."
        ),
        canonical_response=(
            '{"narrative": "Valdren\'s two crises converge: moor industrialization and '
            'thornmere famine push migration patterns the crown has not seen in decades.", '
            '"threads": [{"headline": "Internal migration crisis", '
            '"content_tags": ["migration", "social_pressure"], '
            '"relationship": "open", "parent_thread_id": null}], '
            '"call_wes": false}'
        ),
    ),
    LLMFixture(
        code="wns_layer6",
        tier=TIER_WNS,
        description="WNS NL6 nation-to-world seam weaver.",
        canonical_system_prompt="Identify cross-national narrative seams.",
        canonical_user_prompt=(
            "Active NL5 states:\n"
            "- valdren: migration crisis, industrial surge\n"
            "- khoros: quiet"
        ),
        canonical_response=(
            '{"narrative": "The world\'s narrative centers on Valdren; its neighbors '
            'have not yet felt the migration wave but will.", '
            '"threads": [], "call_wes": false}'
        ),
    ),
    LLMFixture(
        code="wns_layer7",
        tier=TIER_WNS,
        description="WNS NL7 world embroiderer.",
        canonical_system_prompt=(
            "Embroider the world's current narrative from NL6 and WMS L7."
        ),
        canonical_user_prompt=(
            "NL6: Valdren-centered world.\n"
            "WMS L7: world shifting; Valdren dominant."
        ),
        canonical_response=(
            '{"narrative": "The world watches Valdren. A nation reshaping itself is a '
            'long story; the threads are opening faster than they are closing.", '
            '"dominant_arcs": ["valdren_restructuring"], '
            '"dominant_regions": ["ashfall_moors", "thornmere"], '
            '"dominant_factions": [], '
            '"severity": "significant", '
            '"call_wes": false}'
        ),
    ),
]


# ── WES (v4 new) ──────────────────────────────────────────────────────

_WES_FIXTURES = [
    LLMFixture(
        code="wes_execution_planner",
        tier=TIER_WES,
        description=(
            "WES Tier 1 planner. Takes a WESContextBundle, produces a WESPlan "
            "(ordered tool steps with dependencies)."
        ),
        canonical_system_prompt=(
            "You are the execution planner. You receive a context bundle with "
            "a directive; decompose it into a plan of tool invocations. Honor "
            "the firing tier's scope rules."
        ),
        canonical_user_prompt=(
            "Bundle:\n"
            "  firing_tier: 4 (region-scale)\n"
            "  directive: 'Generate content responding to the moors\\' economic "
            "realignment: new faction interests, new NPCs drawn to copper trade.'\n"
            "  narrative_context: Ashfall Moors restructuring around copper.\n"
            "  delta: 4 new bandit skirmishes; 2 guild-member defections."
        ),
        canonical_response=(
            '{"plan_id": "plan_001", "source_bundle_id": "bundle_001", '
            '"steps": ['
            '{"step_id": "s1", "tool": "materials", "intent": "new T2 copper variant unique to the moors", '
            '"depends_on": [], "slots": {"tier": 2, "biome": "moors"}}, '
            '{"step_id": "s2", "tool": "skills", "intent": "bleed-themed lash skill for moors raiders", '
            '"depends_on": [], "slots": {"domain": "physical", "geometry": "single"}}, '
            '{"step_id": "s3", "tool": "hostiles", "intent": "new bandit type exploiting copper trade", '
            '"depends_on": ["s1", "s2"], "slots": {"tier": 2, "biome": "moors", "role": "raider"}}'
            '], '
            '"rationale": "Region-scope firing: add 1 material + 1 skill + 1 hostile tied to the economic arc. Hostile depends on both. No world-shaking content.", '
            '"abandoned": false}'
        ),
    ),
    LLMFixture(
        code="wes_hub_hostiles",
        tier=TIER_WES,
        description=(
            "WES Tier 2 hub for hostiles. Non-adaptive — emits an XML batch of "
            "ExecutorSpecs in one pass."
        ),
        canonical_system_prompt=(
            "You are the hostiles hub. Take one plan step and emit an XML-tagged "
            "batch of specs in one pass. Do not wait to revise."
        ),
        canonical_user_prompt=(
            "Plan step: 'new bandit type exploiting copper trade' (tier 2, moors, raider)\n"
            "Bundle slice: copper-trade-focus thread active."
        ),
        canonical_response=(
            '<specs plan_step_id="s2" count="1">\n'
            '  <spec id="spec_001" intent="moors bandit raider specializing in caravan '
            'ambushes on the copper road" '
            'hard_constraints=\'{"tier": 2, "biome": "moors", "role": "raider"}\' '
            'flavor_hints=\'{"name_hint": "Copperlash Rider", "prose_fragment": "quick, greedy"}\' '
            'cross_ref_hints=\'{}\' />\n'
            "</specs>"
        ),
    ),
    LLMFixture(
        code="wes_hub_materials",
        tier=TIER_WES,
        description="WES Tier 2 hub for materials.",
        canonical_system_prompt="You are the materials hub. Emit XML batch.",
        canonical_user_prompt=(
            "Plan step: T2 copper variant unique to moors. Bundle: moors copper trade."
        ),
        canonical_response=(
            '<specs plan_step_id="s1" count="1">\n'
            '  <spec id="spec_002" intent="moors-specific copper variant with '
            'weathered acid resistance" '
            'hard_constraints=\'{"tier": 2, "category": "ore", "biome": "moors"}\' '
            'flavor_hints=\'{"name_hint": "Moors Copper", "properties": ["acid_resistant"]}\' '
            'cross_ref_hints=\'{}\' />\n'
            "</specs>"
        ),
    ),
    LLMFixture(
        code="wes_hub_nodes",
        tier=TIER_WES,
        description="WES Tier 2 hub for resource nodes.",
        canonical_system_prompt="You are the nodes hub. Emit XML batch.",
        canonical_user_prompt="Plan step: node yielding moors copper.",
        canonical_response=(
            '<specs plan_step_id="s3" count="1">\n'
            '  <spec id="spec_003" intent="cliff-face copper seam node in moors" '
            'hard_constraints=\'{"material_id": "moors_copper", "biome": "moors", "tool_required": "pickaxe"}\' '
            'flavor_hints=\'{"rarity": "uncommon"}\' '
            'cross_ref_hints=\'{"material_id": "moors_copper"}\' />\n'
            "</specs>"
        ),
    ),
    LLMFixture(
        code="wes_hub_skills",
        tier=TIER_WES,
        description="WES Tier 2 hub for skills.",
        canonical_system_prompt=(
            "You are the skills hub. Emit XML batch. Compose from existing tags only."
        ),
        canonical_user_prompt="Plan step: copper-themed physical skill for tier 2 bandits.",
        canonical_response=(
            '<specs plan_step_id="s4" count="1">\n'
            '  <spec id="spec_004" intent="copper-stained gash, bleed-focused melee" '
            'hard_constraints=\'{"domain": "physical", "geometry": "single", "status_tags": ["bleed"]}\' '
            'flavor_hints=\'{"name_hint": "Copperlash Gash"}\' '
            'cross_ref_hints=\'{}\' />\n'
            "</specs>"
        ),
    ),
    LLMFixture(
        code="wes_hub_titles",
        tier=TIER_WES,
        description="WES Tier 2 hub for titles.",
        canonical_system_prompt="You are the titles hub. Emit XML batch.",
        canonical_user_prompt="Plan step: title for moors bandit slayers.",
        canonical_response=(
            '<specs plan_step_id="s5" count="1">\n'
            '  <spec id="spec_005" intent="title rewarding anti-bandit play in moors" '
            'hard_constraints=\'{"category": "combat", "tier": "apprentice", '
            '"unlock_stat": "enemies_defeated_bandit", "unlock_threshold": 20}\' '
            'flavor_hints=\'{"name_hint": "Moors Reaver"}\' '
            'cross_ref_hints=\'{}\' />\n'
            "</specs>"
        ),
    ),
    LLMFixture(
        code="wes_tool_hostiles",
        tier=TIER_WES,
        description=(
            "WES Tier 3 executor_tool for hostiles. Emits one hostile JSON "
            "matching hostiles-1.JSON schema (enemyId + nested stats + "
            "qualitative drops + aiPattern with specialAbilities referring "
            "to existing abilities library + metadata.{narrative, tags}). "
            "Does NOT invent new abilities — atomic co-gen handled by a "
            "separate plan step if needed."
        ),
        canonical_system_prompt=(
            "You are the hostiles executor_tool. Given one ExecutorSpec, "
            "emit one hostile JSON. Categories: beast/ooze/insect/construct/"
            "undead/elemental/aberration/humanoid/dragon. Drops use "
            "quantity:[min,max] array and qualitative chance. aiPattern."
            "specialAbilities references existing abilities only. No prose."
        ),
        canonical_user_prompt=(
            "Spec id: spec_005 (plan step s5)\n"
            "Item intent: moors bandit raider specializing in caravan ambushes\n"
            "Hard constraints: {\"tier\": 2, \"biome\": \"moors\", "
            "\"role\": \"raider\"}\n"
            "Flavor hints: {\"theme\": \"moors raider with copper-weighted whip\"}\n"
            "Cross-ref hints: {\"materialId\": \"moors_copper\", "
            "\"skillId\": \"copperlash_gash\"}\n\n"
            "Emit one hostile JSON following the schema."
        ),
        canonical_response=(
            '{"enemyId": "copperlash_rider", "name": "Copperlash Rider", '
            '"tier": 2, "category": "humanoid", "behavior": "aggressive_pack", '
            '"stats": {"health": 180, "damage": [22, 30], "defense": 14, '
            '"speed": 1.3, "aggroRange": 7, "attackSpeed": 1.1}, '
            '"drops": [{"materialId": "moors_copper", "quantity": [1, 3], '
            '"chance": "moderate"}], '
            '"aiPattern": {"defaultState": "patrol", '
            '"aggroOnDamage": true, "aggroOnProximity": true, '
            '"fleeAtHealth": 0.15, "callForHelpRadius": 10, '
            '"packCoordination": true, '
            '"specialAbilities": ["leap_attack"]}, '
            '"skills": ["copperlash_gash"], '
            '"metadata": {"narrative": "Moors raiders in boiled-copper mail, '
            'swinging short weighted whips from the backs of salt-caked '
            'ponies. They ride in pairs — one harrier, one finisher — and '
            'break contact the moment numbers turn against them.", '
            '"tags": ["humanoid", "aggressive", "mid-game", "physical"]}}'
        ),
        notes=(
            "Cross-refs: drops.materialId moors_copper <- wes_tool_materials; "
            "skills copperlash_gash <- wes_tool_skills; "
            "specialAbilities.leap_attack <- existing hostiles-1.JSON abilities "
            "block (no co-gen needed). xref_rules._extract_hostile_xrefs "
            "reads both drops[].materialId + skills[]."
        ),
    ),
    LLMFixture(
        code="wes_tool_materials",
        tier=TIER_WES,
        description=(
            "WES Tier 3 executor_tool for materials. Emits one material JSON "
            "matching items-materials-1.JSON schema (materialId + metadata.tags "
            "+ metadata.narrative, categories locked to metal/wood/stone/"
            "elemental/monster_drop, rarities locked to common..legendary)."
        ),
        canonical_system_prompt=(
            "You are the materials executor_tool. Given one ExecutorSpec, "
            "emit one material JSON: materialId (snake_case), name (Title "
            "Case), tier (1-4), category (one of metal/wood/stone/elemental/"
            "monster_drop), rarity (one of common/uncommon/rare/epic/"
            "legendary), metadata.{narrative, tags (2-5 from allow-list)}. "
            "No prose."
        ),
        canonical_user_prompt=(
            "Spec id: spec_001 (plan step s1)\n"
            "Item intent: moors copper variant with acid resistance\n"
            "Hard constraints: {\"tier\": 2, \"category\": \"metal\", \"biome\": \"moors\"}\n"
            "Flavor hints: {\"name_hint\": \"Moors Copper\"}\n"
            "Cross-ref hints: {}\n\n"
            "Emit one material JSON following the schema."
        ),
        canonical_response=(
            '{"materialId": "moors_copper", "name": "Moors Copper", '
            '"tier": 2, "category": "metal", "rarity": "uncommon", '
            '"metadata": {"narrative": "A pitted red-green ore dragged from '
            'the fog-wrapped cliffs of the windward moors. Salt-etched veins '
            'thread its matrix, and smiths say the resulting ingots ring thinly '
            'when struck — a prized sign of honest metal.", '
            '"tags": ["metal", "uncommon", "standard"]}}'
        ),
        notes=(
            "Schema matches live items-materials-1.JSON shape so "
            "ContentRegistry ingestion via xref_rules._get_content_id "
            "(accepts both materialId + material_id) lands cleanly."
        ),
    ),
    LLMFixture(
        code="wes_tool_nodes",
        tier=TIER_WES,
        description=(
            "WES Tier 3 executor_tool for resource nodes. Emits one node JSON "
            "matching resource-node-1.JSON schema (resourceId + category + "
            "requiredTool + baseHealth + drops[] + respawnTime + "
            "metadata.{narrative, tags}). ResourceType was refactored to a "
            "namespace class post-2026-04-24 — new resourceIds are runtime-valid."
        ),
        canonical_system_prompt=(
            "You are the nodes executor_tool. Given one ExecutorSpec, emit "
            "one resource-node JSON: resourceId (snake_case), name, category "
            "(tree/ore/stone/fishing), tier (1-4), requiredTool (axe/pickaxe/"
            "fishing_rod), baseHealth (T1=100..T4=800), drops[{materialId, "
            "quantity, chance}] (quantities few/several/many/abundant, "
            "chances guaranteed/high/moderate/low/rare/improbable), "
            "respawnTime (fast/normal/quick/slow/very_slow/null), "
            "metadata.{narrative, tags from allow-list}. No prose."
        ),
        canonical_user_prompt=(
            "Spec id: spec_002 (plan step s2)\n"
            "Item intent: cliff-face copper seam matching the moors biome\n"
            "Hard constraints: {\"tier\": 2, \"category\": \"ore\", \"biome\": \"moors\"}\n"
            "Flavor hints: {\"name_hint\": \"Moors Copper Seam\", \"tool\": \"pickaxe\"}\n"
            "Cross-ref hints: {\"materialId\": \"moors_copper\"}\n\n"
            "Emit one resource-node JSON following the schema."
        ),
        canonical_response=(
            '{"resourceId": "moors_copper_seam", "name": "Moors Copper Seam", '
            '"category": "ore", "tier": 2, "requiredTool": "pickaxe", '
            '"baseHealth": 200, '
            '"drops": [{"materialId": "moors_copper", "quantity": "several", '
            '"chance": "high"}], '
            '"respawnTime": "normal", '
            '"metadata": {"narrative": "An exposed seam of red-green copper '
            'knotted through the cliff face, where the salt-wind has carved '
            'channels deep enough to rest a pick in. Local miners call these '
            '\\u0027honest walls\\u0027 — the copper comes loose in clean '
            'shards if you work with the stone rather than against it.", '
            '"tags": ["ore", "metal", "standard"]}}'
        ),
        notes=(
            "Schema matches live resource-node-1.JSON shape. "
            "xref_rules._extract_node_xrefs reads either materialId or "
            "material_id from drops[], so either casing is tolerated. "
            "The drops[].materialId must resolve to a committed material "
            "(orphan check) — this fixture cross-refs 'moors_copper' which "
            "is emitted by wes_tool_materials."
        ),
    ),
    LLMFixture(
        code="wes_tool_skills",
        tier=TIER_WES,
        description=(
            "WES Tier 3 executor_tool for skills. Emits one skill JSON "
            "matching skills-skills-1.JSON schema (skillId + name + tier + "
            "rarity + categories[1-3] + description + narrative + "
            "tags[2-5 from descriptive allow-list] + effect{type, category, "
            "magnitude, target, duration, additionalEffects} + cost{mana, "
            "cooldown} + requirements{characterLevel, stats, titles})."
        ),
        canonical_system_prompt=(
            "You are the skills executor_tool. Given one ExecutorSpec, emit "
            "one skill JSON. tier 1-4, rarity from common..mythic, categories "
            "from the 15-value allow-list, effect.type from 10 values with "
            "locked per-type category constraints, magnitude minor..extreme, "
            "duration instant..extended, target self/enemy/resource_node/"
            "area, stats keys STR/DEF/VIT/LCK/AGI/INT. No prose."
        ),
        canonical_user_prompt=(
            "Spec id: spec_003 (plan step s3)\n"
            "Item intent: copperlash gash — moors raider bleeding strike\n"
            "Hard constraints: {\"tier\": 2, \"effect_type\": \"devastate\", "
            "\"effect_category\": \"damage\"}\n"
            "Flavor hints: {\"theme\": \"moors raider, copper-weighted whip\"}\n"
            "Cross-ref hints: {}\n\n"
            "Emit one skill JSON following the schema."
        ),
        canonical_response=(
            '{"skillId": "copperlash_gash", "name": "Copperlash Gash", '
            '"tier": 2, "rarity": "uncommon", '
            '"categories": ["combat"], '
            '"description": "A lash-strike with a copper-weighted whip that '
            'opens a bleeding wound.", '
            '"narrative": "Moors raiders favor the copperlash — a short whip '
            'weighted with ore slugs that draws deep cuts the salt wind salts '
            'further.", '
            '"tags": ["damage", "combat", "single_hit"], '
            '"effect": {"type": "devastate", "category": "damage", '
            '"magnitude": "moderate", "target": "enemy", "duration": "instant", '
            '"additionalEffects": []}, '
            '"cost": {"mana": 60, "cooldown": 180}, '
            '"requirements": {"characterLevel": 5, '
            '"stats": {"STR": 6, "AGI": 4}, "titles": []}}'
        ),
        notes=(
            "skillId matches the skill reference in wes_tool_hostiles drops/"
            "aiPattern so cross-refs resolve. Effect type+category pair must "
            "validate against the type->categories matrix (devastate supports "
            "damage/mining/combat)."
        ),
    ),
    LLMFixture(
        code="wes_tool_titles",
        tier=TIER_WES,
        description=(
            "WES Tier 3 executor_tool for titles. Emits one title JSON "
            "matching titles-1.JSON schema (titleId + titleType + "
            "difficultyTier + bonuses dict + prerequisites.conditions[] + "
            "acquisitionMethod + generationChance + isHidden + narrative). "
            "Bonuses use consumer-verified camelCase keys resolved by "
            "TitleSystem.get_total_bonus normalizer (Prereq B)."
        ),
        canonical_system_prompt=(
            "You are the titles executor_tool. Given one ExecutorSpec, emit "
            "one title JSON. titleType from [combat,crafting,gathering,"
            "utility]. difficultyTier from [novice,apprentice,journeyman,"
            "expert,master,special]. Bonuses from the consumer-verified "
            "allow-list. Prerequisites.conditions[] with type-keyed objects "
            "(level/stat_tracker/title/skill/quest/class/stat). "
            "acquisitionMethod from 4 values paired with tier. No prose."
        ),
        canonical_user_prompt=(
            "Spec id: spec_004 (plan step s4)\n"
            "Item intent: apprentice-tier combat title earned via moors raider kills\n"
            "Hard constraints: {\"tier\": \"apprentice\", \"titleType\": \"combat\"}\n"
            "Flavor hints: {\"theme\": \"moors, reaver, kills\"}\n"
            "Cross-ref hints: {}\n\n"
            "Emit one title JSON following the schema."
        ),
        canonical_response=(
            '{"titleId": "apprentice_moors_reaver", '
            '"name": "Apprentice Moors Reaver", '
            '"titleType": "combat", "difficultyTier": "apprentice", '
            '"description": "The moors remember you. Your blade remembers them.", '
            '"bonuses": {"meleeDamage": 0.25, "criticalChance": 0.05}, '
            '"prerequisites": {"conditions": ['
            '{"type": "stat_tracker", '
            '"stat_path": "combat_kills.total_kills", "min_value": 500}, '
            '{"type": "level", "min_level": 5}]}, '
            '"acquisitionMethod": "event_based_rng", '
            '"generationChance": 0.20, '
            '"isHidden": false, '
            '"narrative": "You have cut down enough copperlash riders to know '
            'their rhythms in your sleep. The moors answer your arrival with a '
            'silence that carries down into the fog."}'
        ),
        notes=(
            "Bonus keys 'meleeDamage' + 'criticalChance' resolve via Prereq B "
            "normalizer (camelCase -> snake_case -> 'melee_damage' / "
            "'crit_chance' stored) so combat_manager get_total_bonus('meleeDamage') "
            "calls hit these at runtime. stat_tracker path 'combat_kills."
            "total_kills' is in the verified allow-list."
        ),
    ),
    LLMFixture(
        code="wes_supervisor",
        tier=TIER_WES,
        description=(
            "WES supervisor. Reads all tier logs for a plan pass; outputs a "
            "common-sense verdict + optional rerun instructions."
        ),
        canonical_system_prompt=(
            "You are the WES supervisor. Your single authority is to trigger "
            "a rerun with adjusted instructions. Check: does the generated "
            "content match the directive and bundle context?"
        ),
        canonical_user_prompt=(
            "Plan bundle directive: 'copper-trade economic realignment'.\n"
            "Staged content: 1 material (moors_copper), 1 hostile (copperlash_rider). "
            "Both copper-themed. Hostile drops moors_copper. Clean."
        ),
        canonical_response=(
            '{"verdict": "pass", "rerun": false, "notes": '
            '"Material and hostile are both on-directive. Cross-ref clean. Commit approved."}'
        ),
    ),
]


# ── NPC dialogue (pre-generated speech-banks — CC6) ────────────────────

_NPC_FIXTURES = [
    LLMFixture(
        code="npc_dialogue_speechbank",
        tier=TIER_NPC,
        description=(
            "NPC speech-bank generator. Generates a bounded bank of lines per "
            "NPC per content-update window. Mention extractor runs on this output."
        ),
        canonical_system_prompt=(
            "You are NPC 'gareth_smith' at locality:tarmouth:ironrow. Produce a "
            "speech-bank JSON with greeting, quest-accept, quest-turnin, and "
            "closing lines. Mention nearby factions/events organically."
        ),
        canonical_user_prompt=(
            "Current world state: Ashfall Moors restructuring; copper trade booming; "
            "bandit skirmishes increasing. Local: smithing guild losing apprentices."
        ),
        canonical_response=(
            '{"npc_id": "gareth_smith", "speech_bank": {'
            '"greeting": "Still here, are you? Good. Half my apprentices ran off '
            'to the copperdocks. Pays better, they say. Fools.", '
            '"quest_accept": "Aye, I\'ll take that work. Watch the north road — '
            'Copperlash Riders have been bold lately.", '
            '"quest_turnin": "Well done. You\'re a steadier hand than the ones '
            'I raised. Here — take this.", '
            '"closing": "Off with you, then. Come back when the road kills someone."}, '
            '"mentions": [{"entity": "copperlash_riders", "claim_type": "rumor", "significance": "high"}, '
            '{"entity": "copperdocks", "claim_type": "observation", "significance": "medium"}]}'
        ),
    ),
]


# ── Registration ──────────────────────────────────────────────────────

def _register_all() -> None:
    reg = get_fixture_registry()
    for f in _WMS_FIXTURES + _WNS_FIXTURES + _WES_FIXTURES + _NPC_FIXTURES:
        if not reg.has(f.code):
            reg.register(f)


_register_all()

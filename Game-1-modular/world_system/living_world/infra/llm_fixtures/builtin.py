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
        code="wes_hub_chunks",
        tier=TIER_WES,
        description=(
            "WES Tier 2 hub for chunks (NEW domain). Decomposes a chunk "
            "step into XML batch of ExecutorSpecs for wes_tool_chunks."
        ),
        canonical_system_prompt=(
            "You are the chunks hub. Emit XML batch. Honor category/theme "
            "enums. Cross-refs to nodes/hostiles must resolve."
        ),
        canonical_user_prompt=(
            "Plan step: dangerous moors biome featuring copper seams + "
            "copperlash riders.\nBundle: copper-trade pressure on moors."
        ),
        canonical_response=(
            '<specs plan_step_id="s6" count="1">\n'
            '  <spec id="spec_006" intent="dangerous moors biome featuring '
            'rust-veined cliffs and copper seams — territory of the '
            'copperlash riders" '
            'hard_constraints=\'{"category": "dangerous", "theme": "quarry", '
            '"biome": "moors", "tier_anchor": 2}\' '
            'flavor_hints=\'{"name_hint": "Dangerous Copper Moors", '
            '"prose_fragment": "windswept heath where rust-veined cliffs '
            'meet boggy flats", '
            '"thematic_anchors": ["salt", "copper", "moors"], '
            '"adjacency_intent": ["rocky_highlands", "dangerous_quarry"]}\' '
            'cross_ref_hints=\'{"primary_resource_ids": ["moors_copper_seam"], '
            '"primary_enemy_ids": ["copperlash_rider"]}\' />\n'
            "</specs>"
        ),
    ),
    LLMFixture(
        code="wes_hub_npcs",
        tier=TIER_WES,
        description=(
            "WES Tier 2 hub for NPCs (NEW domain). Decomposes an NPC step "
            "into XML batch of ExecutorSpecs for wes_tool_npcs. home_chunk "
            "is load-bearing — drives speechbank cultural tone downstream."
        ),
        canonical_system_prompt=(
            "You are the NPCs hub. Emit XML batch. home_chunk + "
            "teachableSkills must resolve. Faction tags emergent."
        ),
        canonical_user_prompt=(
            "Plan step: a captain for the Copperlash Rider line, hardened "
            "by loss and anchored to the moors-stone.\n"
            "Bundle: moors-hubtown war thread active."
        ),
        canonical_response=(
            '<specs plan_step_id="s7" count="1">\n'
            '  <spec id="spec_007" intent="a captain of the Copperlash '
            'Rider line, hardened by the loss of a brother on the '
            'moors-stone — issues vendetta quests against hubtown" '
            'hard_constraints=\'{"home_chunk": "dangerous_copper_moors", '
            '"primary_faction": "guild:moors_raiders", "role": "captain", '
            '"tier": 2, "is_questgiver": true}\' '
            'flavor_hints=\'{"name_hint": "Captain Vell Sarn", '
            '"title_hint": "Copperlash Captain", '
            '"prose_fragment": "buried his brother on the moors-stone three '
            'winters ago; commands the longest copperlash line on the salt reach", '
            "\"voice_anchor\": \"clipped, salt-dry, names things by their parts\", "
            '"thematic_anchors": ["salt", "copper", "moors-stone", "brother-who-fell"]}\' '
            'cross_ref_hints=\'{"home_chunk": "dangerous_copper_moors", '
            '"teachable_skill_ids": ["copperlash_gash"], '
            '"affinity_seed_factions": ["guild:moors_raiders", '
            '"region:salt_moors", "family:sarn_clan", "guild:hubtown_militia"]}\' />\n'
            "</specs>"
        ),
    ),
    LLMFixture(
        code="wes_hub_quests",
        tier=TIER_WES,
        description=(
            "WES Tier 2 hub for quests (NEW domain). Decomposes a quest "
            "step into XML batch of ExecutorSpecs for wes_tool_quests. "
            "Static prose only — concrete reward numbers are NOT this "
            "tier's concern."
        ),
        canonical_system_prompt=(
            "You are the quests hub. Emit XML batch. Cross-refs to NPCs / "
            "objective targets / titles / chained quests must resolve. "
            "Reward hints are PROSE only."
        ),
        canonical_user_prompt=(
            "Plan step: vendetta hunt issued by Captain Vell against his "
            "own copperlash riders for ambushing his line.\n"
            "Bundle: moors-hubtown war thread."
        ),
        canonical_response=(
            '<specs plan_step_id="s8" count="1">\n'
            '  <spec id="spec_008" intent="vendetta hunt issued by Captain '
            'Vell against his own copperlash riders for ambushing his '
            'line at the moors-stone" '
            'hard_constraints=\'{"given_by": "moors_copperlash_captain", '
            '"return_to": "moors_copperlash_captain", "quest_type": '
            '"side", "tier": 2, "objective_type": "kill_target"}\' '
            'flavor_hints=\'{"name_hint": "The Salt Reach Hunt", '
            "\"prose_fragment\": \"three for three — the salt remembers what mouths forget\", "
            '"thematic_anchors": ["vendetta", "salt", "copper", "moors-stone"], '
            "\"summary_hint\": \"a captain's nod, a copperlash whip from his own hand, and silver enough for a tavern week\", "
            '"experience_hint": "moderate", "tier_hint": 2, '
            '"difficulty_hint": "moderate"}\' '
            'cross_ref_hints=\'{"given_by_npc_id": "moors_copperlash_captain", '
            '"target_id": "copperlash_rider", "target_tool": "hostiles", '
            '"title_hint": "apprentice_moors_reaver", '
            '"expiration_npc_id": "moors_copperlash_captain", '
            '"wns_thread": "moors_hubtown_war"}\' />\n'
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
        code="wes_tool_chunks",
        tier=TIER_WES,
        description=(
            "WES Tier 3 executor_tool for CHUNK TEMPLATES (new biome recipes, "
            "not specific chunk instances). Emits one template JSON matching "
            "Chunk-templates-2.JSON shape (chunkType + category + theme + "
            "resourceDensity dict + enemySpawns dict + generationRules + "
            "metadata). NEW tool domain — not in original v4 P0-P9. "
            "Post-2026-04-24 ChunkType namespace-class refactor means new "
            "chunkType strings are runtime-valid without code edits."
        ),
        canonical_system_prompt=(
            "You are the chunks executor_tool. Given one ExecutorSpec, emit "
            "one chunk-template JSON: chunkType (snake_case, new OR existing), "
            "name, category (peaceful/dangerous/rare/water/rare_water), theme "
            "(forest/quarry/cave/water), resourceDensity{resourceId: "
            "{density, tierBias}}, enemySpawns{enemyId: {density, tier}}, "
            "generationRules{rollWeight, spawnAreaAllowed, "
            "adjacencyPreference[]}, metadata{narrative, tags}. "
            "Cross-refs must resolve. No prose."
        ),
        canonical_user_prompt=(
            "Spec id: spec_006 (plan step s6)\n"
            "Item intent: dangerous moors biome featuring the new copper seam "
            "nodes and copperlash riders\n"
            "Hard constraints: {\"category\": \"dangerous\", "
            "\"theme\": \"quarry\"}\n"
            "Flavor hints: {\"theme\": \"salt-swept moors with rust-veined "
            "cliffs\"}\n"
            "Cross-ref hints: {\"resourceId\": \"moors_copper_seam\", "
            "\"enemyId\": \"copperlash_rider\"}\n\n"
            "Emit one chunk-template JSON following the schema."
        ),
        canonical_response=(
            '{"chunkType": "dangerous_copper_moors", '
            '"name": "Dangerous Copper Moors", '
            '"category": "dangerous", "theme": "quarry", '
            '"resourceDensity": {'
            '"moors_copper_seam": {"density": "high", "tierBias": "mid"}, '
            '"limestone_outcrop": {"density": "moderate", "tierBias": "low"}}, '
            '"enemySpawns": {'
            '"copperlash_rider": {"density": "moderate", "tier": 2}}, '
            '"generationRules": {"rollWeight": 3, '
            '"spawnAreaAllowed": false, '
            '"adjacencyPreference": ["rocky_highlands", "dangerous_quarry"]}, '
            '"metadata": {"narrative": "Windswept heath where rust-veined '
            'cliffs meet boggy flats — the air smells of brine and green '
            'copper. Moors raiders work the high trails, and the stone itself '
            'sometimes shifts underfoot where old mining tunnels have '
            'collapsed.", '
            '"tags": ["dangerous", "mid-game", "ore-quality", "harsh", '
            '"exposed"]}}'
        ),
        notes=(
            "Cross-refs: resourceDensity.moors_copper_seam <- wes_tool_nodes; "
            "enemySpawns.copperlash_rider <- wes_tool_hostiles; "
            "limestone_outcrop is existing sacred resource. chunkType "
            "'dangerous_copper_moors' is a NEW type — valid at runtime thanks "
            "to the post-2026-04-24 ChunkType namespace-class refactor. Full "
            "content_registry plumbing (reg_chunks table, xref extractor, "
            "tool_registry entry) is follow-up work; fixture-only for now."
        ),
    ),
    LLMFixture(
        code="wes_tool_npcs",
        tier=TIER_WES,
        description=(
            "WES Tier 3 executor_tool for NPCs (v3 schema). Emits one NPC JSON "
            "matching npcs-3.JSON / data/models/npcs.py NPCDefinition. v3 "
            "splits static design data (this output) from dynamic SQLite state "
            "(faction system tables: npc_dynamic_state, npc_dialogue_log, "
            "npc_affinity). Personality is INLINE per-NPC (no template FK); "
            "speechbank carries birth-time canned dialogue + cultural "
            "phrase_bank for LLM context priming."
        ),
        canonical_system_prompt=(
            "You are the NPCs executor_tool. Given one ExecutorSpec, emit one "
            "NPC v3 JSON: npc_id, name, title, narrative (immutable past, 2-4 "
            "sentences), personality{voice, knowledge_domains, "
            "reaction_modifiers, gossip_interests, base_emotional_state, "
            "dialogue_style}, locality{home_chunk}, faction{primary, "
            "belonging_tags[]}, affinity_seeds{tag:int} (must include "
            "_player), services, unlockConditions, speechbank{greeting[], "
            "farewell[], idle_barks[], quest_offer, quest_complete, "
            "phrase_bank{exclamations, oaths, endearments_friend, "
            "endearments_enemy, fillers}}, quests, position, sprite_color, "
            "interaction_radius, metadata{tags}. home_chunk + teachableSkills "
            "+ quests must cross-ref. Faction tags are emergent (namespace "
            "conventions only). No prose."
        ),
        canonical_user_prompt=(
            "Spec id: spec_007 (plan step s7)\n"
            "Item intent: a captain of the Copperlash Rider line, hardened by "
            "the loss of a brother, anchored to the moors-stone\n"
            "Hard constraints: {\"home_chunk\": \"dangerous_copper_moors\", "
            "\"primary_faction\": \"guild:moors_raiders\"}\n"
            "Flavor hints: {\"theme\": \"salt-dry, clipped speech, names "
            "things by their parts\"}\n"
            "Cross-ref hints: {\"home_chunk\": \"dangerous_copper_moors\", "
            "\"teachable\": [\"copperlash_gash\"], \"rival_faction\": "
            "\"guild:hubtown_militia\"}\n\n"
            "Emit one NPC v3 JSON following the schema."
        ),
        canonical_response=(
            '{"npc_id": "moors_copperlash_captain", '
            '"name": "Captain Vell Sarn", '
            '"title": "Copperlash Captain", '
            '"narrative": "Vell rode his first salt-pony at twelve and led '
            'his first whip-line raid at nineteen. Three winters ago he '
            'buried his brother on the moors-stone after a hubtown ambush, '
            'and the salt has not let him forget it. He commands the longest '
            'copperlash line on the salt reach because no one beneath him '
            'asks twice why the captain rides at the front.", '
            '"personality": {'
            '"voice": "Clipped, salt-dry, prone to long pauses before '
            'answering. Names things by their parts rather than their wholes '
            "— 'the line', 'the stone', 'the brother who fell'.\", "
            '"knowledge_domains": ["combat", "tactics", "weapons", "factions"], '
            '"reaction_modifiers": {'
            '"ENEMY_KILLED": {"enemy_match": ["copperlash_rider"], '
            '"relationship_delta": -0.08, "emotion": "cold", '
            '"description": "Player killed one of his own."}, '
            '"ITEM_CRAFTED": {"discipline_match": "smithing", '
            '"relationship_delta": 0.02, "emotion": "approving"}, '
            '"LEVEL_UP": {"relationship_delta": 0.01, "emotion": "watchful"}}, '
            '"gossip_interests": ["area_danger", "faction_conflict", '
            '"population_change"], '
            '"base_emotional_state": "wary", '
            '"dialogue_style": {"max_response_length": 140, '
            '"formality": "stern", "uses_jargon": true}}, '
            '"locality": {"home_chunk": "dangerous_copper_moors"}, '
            '"faction": {"primary": "guild:moors_raiders", '
            '"belonging_tags": ['
            '{"tag": "guild:moors_raiders", "significance": 0.95, '
            '"role": "captain", "narrative_hooks": "longest copperlash line on the reach"}, '
            '{"tag": "region:salt_moors", "significance": 0.8, '
            '"role": null, "narrative_hooks": "moors-stone burial"}, '
            '{"tag": "family:sarn_clan", "significance": 0.7, '
            '"role": "surviving brother", "narrative_hooks": null}]}, '
            '"affinity_seeds": {"guild:moors_raiders": 95, '
            '"region:salt_moors": 85, "family:sarn_clan": 90, '
            '"guild:hubtown_militia": -85, "_player": 0}, '
            '"services": {"canTrade": false, "canRepair": false, '
            '"canTeach": true, "teachableSkills": ["copperlash_gash"], '
            '"specialServices": []}, '
            '"unlockConditions": {"alwaysAvailable": false, '
            '"characterLevel": 8, "completedQuests": []}, '
            '"speechbank": {'
            '"greeting": ["Speak quick.", '
            "\"You're a long way from forge-light, stranger.\", "
            '"Stand where I can see you."], '
            '"farewell": ["Salt sees.", "Walk light."], '
            '"idle_barks": ['
            '"Copper sings before it dulls.", '
            '"The hubtown line breaks at dusk — every dusk.", '
            '"My brother knew this stone.", '
            '"Three riders went out at dawn. Two came back.", '
            '"Salt remembers what mouths forget.", '
            '"The fog is thick today. Good for us."], '
            "\"quest_offer\": \"There is a thing the line needs done. You'll do it.\", "
            '"quest_complete": "It is done. The salt knows your name now.", '
            '"phrase_bank": {'
            '"exclamations": ["By salt and copper!", "Stone-take it."], '
            "\"oaths\": [\"On the moors-stone, I swear it.\", \"By my brother's name.\"], "
            '"endearments_friend": ["salt-friend", "line-rider"], '
            '"endearments_enemy": ["saltless", "hubtown wretch"], '
            '"fillers": ["aye", "hmph", "speak"]}}, '
            '"quests": [], '
            '"position": {"x": -12.0, "y": 7.0, "z": 0.0}, '
            '"sprite_color": [180, 80, 60], '
            '"interaction_radius": 3.0, '
            '"metadata": {"tags": ["humanoid", "trainer", "veteran", '
            '"mid-game", "questgiver"]}}'
        ),
        notes=(
            "Cross-refs: locality.home_chunk -> wes_tool_chunks "
            "(dangerous_copper_moors); services.teachableSkills -> "
            "wes_tool_skills (copperlash_gash); reaction_modifiers."
            "ENEMY_KILLED.enemy_match -> wes_tool_hostiles "
            "(copperlash_rider). Faction tags (guild:moors_raiders, "
            "region:salt_moors, family:sarn_clan, guild:hubtown_militia) are "
            "emergent — no faction registry validation. affinity_seeds "
            "include the reserved '_player' tag for the NPC's starting "
            "opinion of the player. Dynamic state (current emotion, "
            "relationship drift, dialogue log) is NOT in this output — "
            "lives in faction SQLite tables (npc_dynamic_state, "
            "npc_dialogue_log, npc_affinity) and is initialized at NPC birth "
            "from affinity_seeds. Full content_registry plumbing (reg_npcs "
            "table, xref extractor wired to TOOL_NPCS) is follow-up work."
        ),
    ),
    LLMFixture(
        code="wes_tool_quests",
        tier=TIER_WES,
        description=(
            "WES Tier 3 executor_tool for QUESTS (v3 schema). Emits one "
            "quest JSON matching quests-3.JSON / data/models/quests.py "
            "QuestDefinition. Quest v3 has a TWO-STATE lifecycle: static "
            "JSON (this output) carries PROSE reward estimates only — "
            "concrete numbers are materialized at quest-accept time by a "
            "future resolver. Archive at turn-in records actual outcomes "
            "for WNS narrative continuity (separate WMS-side schema, not "
            "in this output)."
        ),
        canonical_system_prompt=(
            "You are the quests executor_tool. Given one ExecutorSpec, "
            "emit one v3 quest JSON: quest_id, name, title, quest_type "
            "(tutorial/side/main/chain/repeatable/hidden), tier, "
            "description_full{short, long, narrative}, given_by/npc_id/"
            "return_to (cross-ref NPCS), objectives{objective_type "
            "(gather/combat/kill_target/craft/deliver/explore/talk), "
            "items, enemies_killed}, rewards (empty defaults — never "
            "concrete numbers), rewards_prose{summary, experience_hint, "
            "tier_hint, title_hint, skill_hint, item_hints[]}, "
            "requirements{characterLevel, stats, titles, completedQuests, "
            "factionAffinity?}, expiration{type, ...}, progression, "
            "wns_thread_id, completion_dialogue, metadata{narrative, tags, "
            "difficulty, estimatedTime}. Cross-refs must resolve. No prose."
        ),
        canonical_user_prompt=(
            "Spec id: spec_008 (plan step s8)\n"
            "Item intent: a vendetta hunt issued by Captain Vell against "
            "his own copperlash riders for ambushing his line at the "
            "moors-stone\n"
            "Hard constraints: {\"objective_type\": \"kill_target\", "
            "\"target_id\": \"copperlash_rider\", \"quantity\": 3}\n"
            "Flavor hints: {\"theme\": \"vendetta, three-for-three, salt "
            "and copper\"}\n"
            "Cross-ref hints: {\"given_by\": \"moors_copperlash_captain\", "
            "\"target\": \"copperlash_rider\", \"title_hint\": "
            "\"apprentice_moors_reaver\", \"thread\": \"moors_hubtown_war\"}\n\n"
            "Emit one v3 quest JSON following the schema."
        ),
        canonical_response=(
            '{"quest_id": "salt_reach_hunt", '
            '"name": "The Salt Reach Hunt", '
            '"title": "The Salt Reach Hunt", '
            '"quest_type": "side", "tier": 2, '
            '"description_full": {'
            '"short": "Hunt three copperlash riders for Captain Vell.", '
            "\"long\": \"Captain Vell's line was ambushed at the "
            'moors-stone three nights past. He wants three of the '
            'copperlash riders dead in answer. Bring proof.", '
            '"narrative": "Three for three. The salt remembers what mouths forget."}, '
            '"given_by": "moors_copperlash_captain", '
            '"npc_id": "moors_copperlash_captain", '
            '"return_to": "moors_copperlash_captain", '
            '"objectives": {'
            '"objective_type": "kill_target", '
            '"items": [{"target_id": "copperlash_rider", "quantity": 3, '
            '"description": "Slay copperlash riders", "optional": false}], '
            '"enemies_killed": 0}, '
            '"rewards": {"experience": 0, "gold": 0, "health_restore": 0, '
            '"mana_restore": 0, "skills": [], "items": [], "title": "", '
            '"stat_points": 0}, '
            '"rewards_prose": {'
            "\"summary\": \"A captain's nod, a copperlash whip from his "
            'own hand, and silver enough for a tavern week.", '
            '"experience_hint": "moderate", "tier_hint": 2, '
            '"title_hint": "apprentice_moors_reaver", '
            '"skill_hint": null, '
            '"item_hints": ["copperlash whip", "silver penny", "salt-cured rations"]}, '
            '"requirements": {"characterLevel": 5, "stats": {}, '
            '"titles": [], "completedQuests": [], '
            '"factionAffinity": {"guild:moors_raiders": {"min": 20}}}, '
            '"expiration": {"type": "npc_death", '
            '"npc_id": "moors_copperlash_captain"}, '
            '"progression": {"isRepeatable": false, "cooldown": null, '
            '"nextQuest": null, "questChain": "moors_war_chain"}, '
            '"wns_thread_id": "moors_hubtown_war", '
            '"completion_dialogue": ['
            '"It is done. The salt knows your name now.", '
            "\"Take this whip. It cut its last man wrong — it'll cut yours right.\"], "
            '"metadata": {'
            '"narrative": "Faction-driven vendetta quest. Threads into '
            'the moors-hubtown blood line.", '
            '"tags": ["combat", "faction", "mid-game", "vendetta", "hunt"], '
            '"difficulty": "moderate", '
            '"estimatedTime": "20 minutes"}}'
        ),
        notes=(
            "Cross-refs: given_by/npc_id/return_to/expiration.npc_id -> "
            "wes_tool_npcs (moors_copperlash_captain); "
            "objectives.items[].target_id -> wes_tool_hostiles "
            "(copperlash_rider); rewards_prose.title_hint -> wes_tool_titles "
            "(apprentice_moors_reaver). Faction-affinity gate "
            "(guild:moors_raiders >= 20) makes this quest only available "
            "to moors-aligned players. wns_thread_id 'moors_hubtown_war' "
            "links to a WNS narrative thread (future wiring). "
            "rewards_prose carries narrative hints — concrete numerical "
            "rewards are NOT emitted by this tool; the materializer rolls "
            "them at quest-accept time. Archive at turn-in is separate "
            "(WMS-side schema, follow-up work)."
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

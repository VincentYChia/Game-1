# WNS/WES Backwards-Design Pass — Consolidation

*From 11 Feature Trace Documents to a Build Plan*
*Authored: 2026-06-02*
*Anchored on: the user's quest example (the gold standard) + the user's behavior-causal correction (the unification thesis)*

---

## 0. What this is

The 11 trace documents in this directory (`01-quests.md` through `11-trigger-taxonomy.md`) are the inputs to this document. They were authored over four dispatch waves by eleven Opus agents, each anchored on a player-facing artifact (Quest JSON, NPC JSON, etc.) or a cross-cutting concern (orchestration, trigger taxonomy). Each agent applied the same eight-step methodology and walked the same nine-rung WMS creative-extraction checklist.

This document is the consolidation. Not a trace. It synthesizes the eleven into:

- **Section 1** — what the pass produced at a glance
- **Section 2** — the architectural conclusions that survived the pass
- **Section 3** — every gap raised, deduplicated and ranked by leverage
- **Section 4** — shared infrastructure that multiple features want
- **Section 5** — designer-action queue (prose authoring needs)
- **Section 6** — a dependency-ordered build sequence with ship-criteria per phase
- **Section 7** — risk register
- **Section 8** — open questions only the user can resolve
- **Section 9** — what's explicitly OUT of scope
- **Section 10** — how to use this document going forward
- **Appendices** — trace index, gap marker reference, methodology pointers

The pass is complete. This document is the bridge from "design" to "build."

---

## 1. The pass at a glance

Eleven traces. Roughly 6,500 lines combined. **Zero `[WMS-GAP]` markers across all eleven agents.** The nine-rung discipline held universally — every agent who was tempted to claim the WMS couldn't provide something walked the rungs in writing and found the signal reachable through existing surface.

| Trace | Anchor artifact | Wave | Length | Headline finding |
|---|---|---|---|---|
| 01 Quests | Quest JSON | 1 (REFERENCE) | ~600 lines | The pre-generated quest pool architecture. Scroll unfurl masks 2-3s of reward materialization; quest tool fires at cascade time (any latency). |
| 02 NPCs | NPC v3 JSON + dialogue | 2 | ~700 lines | NPCs are the **hub feature** — six other tools need NPC voice data. One publish API serves six consumers. |
| 03 Hostiles | Hostile JSON | 2 | ~500 lines | `EnemyDatabase.reload()` gap is higher priority than the bundle leak for hostiles specifically — database silently degrades on regeneration. |
| 04 Materials | Material JSON | 2 | ~500 lines | Category allow-list mismatch between hub and tool silently emits wrong-category materials. (Recipe-orphan claim was wrong — corrected by user.) |
| 05 Nodes | Resource node JSON | 2 | ~500 lines | **Five silent wiring failures** between WES generation and runtime spawn (xref key mismatch, wrapper-key bypass, missing reload, ID-candidates incomplete, respawn-map drops). |
| 06 Skills | Skill JSON | 2 | ~600 lines | Planner emits skills before NPCs in DAG → teacher narrative doesn't exist when skill tool writes. Solution: pass teacher intent, not narrative. |
| 07 Titles | Title JSON | 2 | ~500 lines | Biographical-snapshot composer is the missing infrastructure. Titles are WMS-primary; no `[WMS-GAP]` despite that. |
| 08 Chunks | Chunk template JSON | 2 | ~500 lines | `geoTypes` collision can silently SUPPRESS sacred biomes. Chunks are the dependency root for nodes/hostiles/materials in the DAG cascade. |
| 09 WNS | Narrative + WNS-to-WES contract | 2 | ~530 lines | **The bundle contract.** Specifies exactly which fields the slice must carry. Also: WNS has no player-facing UI; bridge builds empty `NarrativeDelta`. |
| 10 Orchestration | Planner/Supervisor/RequestLayer decisions | 3 | ~805 lines | **Narrative authority** reframing of `scope_by_firing_tier` (gossip-scale vs. chronicler-scale vs. chronicler-of-ages). DAG ordering generalized rule. Active supervisor template bug found. |
| 11 Trigger Taxonomy | Cross-cutting unification framework | 4 (meta) | ~1,068 lines | **The unification thesis.** Two trigger archetypes (narrative-causal + behavior-causal) feeding one pipeline. The player must not perceive which archetype birthed which content. The skill-evolution prose ambiguity correction (the user's second insight). |

**Quality bar held.** Agent 1's trace was the calibrator. Waves 2-4 matched its depth and channeled the user's mentality (failure modes before requirements, timing as primary anchor, above-templated-baseline benchmarks, personal-shopper minimal-waste sharing, immaculate enumeration). The trace pass is not a checklist — it reads like a senior designer thinking out loud through every branch.

---

## 2. Architectural conclusions

Eight conclusions emerged with the depth and cross-trace convergence to be load-bearing. Each names a specific design commitment with the reasoning that survived the pass. These are the architectural decisions that the build plan inherits.

### 2.1 The unification thesis (Wave 4 spine)

There are two distinct *causes* for content to be generated:

- **Narrative-causal.** A WNS thread reaches a state where new content would make the story better. NPCs are in motion; factions are colliding. The WNS weaver emits `<WES purpose="new-X">` from inside its narrative. Bundle context is narrative-anchored: faction tensions, NPC voices, locality threads, rumors.

- **Behavior-causal.** A WMS milestone trips — the player has used 1,000 potions, killed 500 hostiles of a species, walked 100,000 steps. The WNS interprets the milestone via the daily ledger / activity profile / `StatStore`. The WNS dispatches the same `<WES purpose="new-X">` directive from interpretation rather than from inside narrative. Bundle context is behavior-anchored: activity profile, StatTracker patterns, milestone tag, inferred behavior intent.

Both archetypes feed the **same eight WES tools through the same pipeline**. Mixed-trigger cases (the user's chunks pseudo-trace: NPC rumors of new terrain + exploration milestone → alchemy-themed new chunk that propagates DAG-flavor down to nodes/hostiles/materials) are the canonical full case, not an exception.

**The player perceptual seamlessness is the deliverable.** The player should not be able to tell which archetype birthed which content. The world responds to a 1,000-potion milestone with an instant-heal skill, and to a faction tension with a new bandit camp, and to a mixed trigger with an alchemy-themed biome — and all three should feel like the same world responding to the same player coherently.

The prior 10 traces tunneled in on narrative-causal because Agent 1 (Quests) was the calibrator and quests are heavily NPC-mediated. Wave 4 corrected this. The unification thesis is the document's spine.

### 2.2 The bundle is the substrate (built deterministically by code)

The `WESContextBundle` is the single shared dependency across orchestration. The planner reads it, the supervisor reads its output spec against it, the request layer reads its directive_text, the eight content tools each read a slice of it. **The bundle is where the system either has narrative coherence or doesn't.**

**Discipline note.** The bundle is constructed by deterministic code — the WMS→WNS bridge, the bundle assembler, the BehaviorInterpreter's signal builder. StatStore queries, ledger lookups, tag filters, geographic registry reads, event store adjacent queries all happen through code. The LLM only reads the curated bundle that code prepared for it; the LLM does not query for context. Every "clever coding circumstance" that gathers information lives on the bridge/assembler side, not in the prompt. This is the same discipline as the 9-rung WMS extraction — creative information gathering happens in code, not in chain-of-thought.

Today the bundle has a critical leak. `slice_bundle_for_tool` in `Game-1-modular/world_system/wes/context_bundle.py:342-370` strips `parent_summaries`, `firing_layer_summary`, `geographic_chain`, and the WMS events delta before tools see the spec. Only `flavor_hints.prose_fragment` survives. **This is the single largest source of disconnected-from-narrative content generation across all eight tools.**

Agent 9 specified the post-fix bundle contract. Wave 4 extended it for behavior-causal triggers. The post-fix `BundleToolSlice` carries:

- `firing_layer_summary` — what the weaver just wrote (or, for behavior-causal, the WMS L2 interpretation row)
- `parent_summaries: Dict[str, str]` — cascading parent narratives keyed by `"{layer}:{address}"`
- `geographic_chain: List[Dict]` — locality → world tier briefs with biome / region / description
- `threads_in_focal_address: List[ThreadFragment]` — **full payloads** (content_tags + relationship + parent_thread_id), not just headlines
- `threads_in_parent_addresses: List[ThreadFragment]` — cascading arc context
- `wms_events_since_last: List[WMSLayerRow]` — factual delta (today the builder leaves this empty; must populate)
- `trigger_archetype: str` — `"narrative" | "behavior" | "mixed"`
- `behavior_signal: Optional[BehaviorSignal]` — counter_path, threshold_crossed, activity_profile, inferred_behavior_intent, matching_pool_entries
- `recent_registry_entries` — unchanged

Each hub's `_make_vars` exposes corresponding template variables (`${firing_narrative}`, `${parent_narratives}`, `${geographic_chain}`, `${thread_fragments}`, `${wms_events_summary}`, `${behavior_flavor}`). The fix is approximately **30 lines of code change** in `context_bundle.py`, `execution_planner.py`, and each hub, plus designer prose review of the template variable additions in the planner + each hub's user template.

**One PR. Eight tools win.** This is the highest-leverage fix in the entire system.

### 2.3 The permission table is hardcoded; voice prose filters across tiers

**Correction from earlier draft (2026-06-03).** Agent 10's "narrative authority" framing was poetry on top of what's actually a rules-and-filters table. The architecture has two distinct things:

1. **The permission table.** Hardcoded data per tier: which WES purposes are allowed, which are forbidden, max steps per plan, DAG ordering rules, biome inheritance rules. This is resolute — the planner does not negotiate with it. Tier 2 cannot emit `new-chunk` because the table says no. Tier 7 can emit world-shifts because the table says yes. The table is the unambiguous spec the planner reads at every dispatch.

2. **The voice prose per tier.** Each tier has authored prose that filters how directives sound at that scope. Tier 2 prose sounds like village gossip; tier 7 prose sounds like a chronicler of ages. This is the "filter effect" — the same purpose firing at different tiers comes out with different voice. The prose is data the planner/weaver reads to shape the directive body and the supervisor reads to verify voice-fit.

This is the same architectural shape as WMS. WMS L1 events get tagged and aggregated by rule into L2 narrative rows; each higher layer (L3-L7) has rule-driven aggregation criteria and a defined scope; the voice that catalogs the information varies per layer. WNS is the WMS pattern applied to narratives. **Layers are rule-driven; what each layer expresses is rule-driven; the voice doing the cataloging filters across the rule-driven structure.**

Agent 10's v4 draft (`10-orchestration.md` §8.3) is the right shape for the permission table — per-tier-per-purpose allowed/forbidden lists, step caps, DAG ordering. The voice prose per tier is part of the D2 designer-authoring queue (per-layer voice blocks) cross-referenced with D6's per-purpose shapes at runtime.

Wave 4's `scope_by_behavior_threshold` is the same shape — hardcoded behavior-counter-category permissions plus voice-filtering. Same discipline, different driver.

### 2.4 The DAG ordering rule

Agent 6 (Skills) surfaced an inversion: the planner currently emits `[skills, npcs]` for moors-copper firings — skills before NPCs. When the skill tool writes, the teacher NPC's narrative doesn't exist yet. The skill's narrative is voice-blind to the teacher.

Agent 10's verdict, generalized into a planner-prompt rule:

> **When tool A's narrative content REFERENCES tool B's proper noun (a skill's narrative mentions a teacher, a quest's narrative mentions a giver, an NPC's narrative mentions a home chunk), tool B emits FIRST in the DAG. When tool A's STRUCTURAL field references tool B's id (`teachableSkills`, `enemySpawns`, `drops`), use either co-emission (same plan step) or orphan-cascade (request layer handles).**

This generalizes across all eight tools. NPCs first when a skill or quest will reference them. Materials first when a hostile's drops will reference them. Chunks last (they're spatial substrate; nodes/hostiles/materials inherit from them via flavor_hints, not by narrative reference).

The orphan resolver and request layer were designed for exactly this pattern — when a structural reference points to content that doesn't exist, the cascade fills it in. The DAG ordering rule extends this so narrative references resolve cleanly.

### 2.5 NPCs are the largest narrative-injection surface, not "the hub"

**Correction from earlier draft (2026-06-03).** NPCs are NOT THE hub feature — they're the largest *injection surface* for narrative to the player because dialogue is verbose and ambient. But from the system's point of view, **every content type carries narrative**: quest descriptions, title prose, skill narratives, material lore, chunk descriptions, hostile lore, NPC dialogue. Cross-references between them are the structural linkage that lets narrative compose across types. No single feature owns "the hub" role.

What remains true and useful:

- **`NPCDatabase.get_voice_excerpt(npc_id) -> Dict`** is still a worthwhile API — six other content types reference NPC narrative when authoring their own (Quests' giver narrative, Skills' teacher voice, Titles' granter voice, Hostiles' related-NPC lore, Quest reward adaptation, dialogue speechbank). The API is one of multiple cross-tool sharing patterns, not the central one.
- **Cross-reference schema fields** (`granted_by_quest_id`, `taught_by_npc_id`, `hunted_by_quest_id`, `gather_quest_id`, `rewarded_by_quest_id`, `inherited_from_chunk_id`) are the broader linkage pattern. Every content type can REFERENCE every other content type that birthed it or that's narratively adjacent.
- **The DAG ordering rule (§2.4)** is the rule the planner uses to ensure references resolve. When tool A's narrative references tool B's proper noun, B emits first.

The personal-shopper principle still holds: build cross-reference infrastructure once, share widely, divergence only where flavor genuinely demands it. The earlier "NPCs are the hub" framing concentrated this insight on one feature; the corrected framing distributes it.

### 2.6 Prose ambiguity is a designer feature

The user's second correction, brought forward into Wave 4: skill evolution prose should be **intentionally vague**. Not "kill 50 copperlash riders in the salt moors" (a checklist that destroys mystery). Yes "master its usage in the native environment" (a hook the player must explore).

The principle (refined 2026-06-03 — the binary is wrong; classification is a gradient):

- **Pure structural fields** — xref IDs (must match registry keys), numeric balance values, enum values that code branches on, machine-checked conditions. These must be exact.
- **Pure prose fields** — descriptions, narratives, lore, completion dialogues, chunk narrative descriptions, NPC voice lines. These must be evocative-but-vague.
- **Hybrid / structural-but-prose-eligible** — some fields look structural but should embrace ambiguity. The user's named example was `evolution.requirement` (descriptive only at runtime; code doesn't gate on the prose). Tier descriptors that could be "low/mid/high" rather than "1/2/3/4" if downstream code accepts the looser shape. Title `signature_deeds[]` content. When in doubt: if removing exactness wouldn't break code, the field is eligible for ambiguity.

The classification is per-field judgment, not a global rule. The `prose_ambiguity_directive` fragment (D5) provides patterns the designer can apply per field.

The failure mode the user named (`evolution.requirement` reading "Slay 50 copperlash riders in the salt moors") was the cleanest example across all 10 traces. The same principle applies to: hostile lore, chunk narrative description, title earning-prose, NPC voice lines, completion dialogues, signature_deeds entries, and any structural-adjacent field that downstream code doesn't strictly gate on.

Wave 4 specced a single shared prompt fragment — `prose_ambiguity_directive` — included in every tool's system prompt. Acceptable patterns: "Master its usage in the native environment." "The hand knows before the mind names the wound." "Carries copper from old veins." "The moors have learned your tread." Unacceptable patterns: "Use 100 times." "Kill 50 of X in chunk Y." "Trigger when player.stat > value."

**The principle that distinguishes specific from checklist: specificity anchors the FEEL; enumeration reveals the MECHANIC. Anchor in feel; never reveal the mechanic.**

For behavior-causal artifacts this applies with extra force. A skill that emerged from a 1,000-potion milestone whose narrative reads "earned because the player used 1,000 potions" destroys the illusion of organic world response. The world has noticed; the world does not enumerate.

### 2.7 Behavior-emergence is PRIMARY, not co-equal with NPC narrative

**Correction from earlier draft (2026-06-03).** Behavior-emergence is not one of two equal paths — it is the **primary mode** through which the world recognizes the player. NPC interactions are the *words*; behavior-emergence is the *actions and body language*. Words are clear and helpful, but body language reveals more about what the system thinks of the player and what the player is actually doing. The system's response to the player's *actions* — the skill that emerges from 1,000 potions used, the tier-up hostile after 100 kills, the manifested NPC who has been watching, the alchemy-tinted biome that opens up — is what makes the world feel alive.

Behavior-causal triggers cover all five identity-responsive content types: **Skills, Titles, Hostiles, Quests, NPCs (manifestation-framed)**. Phase 2 (behavior substrate) is therefore the highest-priority architectural addition after Phase 1's bundle propagation fix. The earlier draft positioned NPCs and behavior-causal as co-equal axes; the corrected priority is: behavior-causal is the load-bearing player-recognition mechanism, and NPC narrative is one of several injection surfaces for the response.

**NPC manifestation framing.** NPCs exist narratively the whole time — the king has always been king; the master fletcher of the moors has always been there. The `new-npc` directive doesn't *invent* a person; it *manifests* an already-existing person into the registry when the player's behavior has brought them into proximity or reached a milestone that would plausibly trigger the meeting. A 100-kills-in-the-moors milestone manifests the moors-master who's been watching. An avoidance pattern manifests the kin NPC who comes looking. The prompt-design discipline for `new-npc` behavior-causal triggers must encode this framing: "manifest the person who would plausibly exist in this world that the player has now had reason to encounter" — not "create a new person who exists now."

**Build-order implication.** Phase 2 (behavior substrate) is now the highest-priority Phase 1+ work, above Phase 4 (NPC hub) in importance. The phase numbering stays the same for dependency reasons (Phase 1's bundle propagation unblocks Phase 2), but the IMPORTANCE order is: Phase 0 (plumbing) → Phase 1 (bundle) → Phase 2 (behavior, primary player-recognition) → Phase 3 (designer prose for both archetypes) → Phase 4 (NPC hub, secondary) → Phase 5 (DAG inheritance) → ... .

For Skills specifically: the behavior-causal path is what gives the player the strongest "the world recognizes ME" feeling. The user's potions example is canonical, not speculative. Agent 6 had specced `wes_skill_player_signature` as a future endpoint; Wave 4 promoted it to first-class. The skill schema needs a new `unlockMethod: BehaviorEmergence` (no NPC teacher required). The skill tool's prompt must handle `behavior_signal` directly as a first-class input shape.

For Titles: the pool must EXPAND behavior-causally, not just be evaluated behavior-causally at runtime. When a player crosses a threshold the existing title pool doesn't honor, the pool itself should expand (mint "Whisper-killer" for a 90%-stealth-backstab signature; mint "The Merchant" for a 100k-gold-no-combat negative-pattern).

For Hostiles: kill-count milestones spawn tier-up variants (Copperlash Captain after 100 Copperlash kills); death-by-source patterns spawn teaching encounters (the world recognizes the damage type you keep dying to and emits a hostile whose kit teaches you to handle it); combat-style adaptation spawns anti-strategy hostiles. **This closes the combat-loop response.** Today the loop is: player kills → loot → level. With behavior-causal: player kills 100 → world responds with tier-up + tactical challenge → player adapts. The combat system feels alive rather than treadmill.

For Quests: failure-pattern triggers (10 quest failures → redemption arc with rewards scaling against the recent failures) are the strongest "world recognizes me" quest pattern available, and the cleanest demonstration that the world's response can be SUPPORTIVE, not just iterative-difficulty.

### 2.8 The WMS is sufficient

Eleven traces. Zero `[WMS-GAP]` markers. The 9-rung creative-extraction discipline did its job in every single case.

When agents were tempted to claim WMS insufficiency — player-grievance history with a quest-giver's faction, regional gathering pressure, player-standing-at-NPC-birth, ecosystem census, player skill-learning patterns, locality social network, regional biome composition, cross-session behavior signal, per-locality activity profile — they walked the rungs in writing and resolved each through existing surface (`StatStore` 65 record methods, `daily_ledger`, 33 L2 evaluators, `TriggerManager` history, `event_store` adjacent queries, cross-layer climb, negative-pattern absence-as-signal).

**The WMS substrate is sufficient for v4.** Stringency held. WMS enhancements (deferred future capability) are permitted for backlog tracking but no WMS structural changes block any feature.

The gaps live at the boundary — at the WMS→WNS bridge where milestone events need to actually reach the WNS interpretive layer, and at the WNS→WES bundle where richer fields need to survive the slice.

---

## 3. Gap inventory (every gap, deduplicated, ranked by leverage)

This is the consolidated list of every gap raised across all eleven traces. Deduplicated where multiple agents raised the same gap. Ranked by **leverage** — how many of the eight content tools benefit from each fix.

Markers per the 5-marker taxonomy: `[FRAGMENT-GAP]` / `[WNS-GAP]` / `[WES-SCHEMA-GAP]` (liberal) | `[WMS-ENHANCEMENT]` (deferred) | `[WMS-GAP]` (none).

| ID | Marker | Description | Raised by | Leverage | Effort | Priority |
|---|---|---|---|---|---|---|
| G01 | `[WES-SCHEMA-GAP]` | **Bundle field propagation** — `slice_bundle_for_tool` strips `parent_summaries`, `firing_layer_summary`, `geographic_chain`, full thread payloads, WMS events delta | Agent 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 (universal) | **8 of 8 tools** | ~30 LOC | **P0 — ship first** |
| G02 | `[WNS-GAP]` | **Bridge builds empty `NarrativeDelta`** — `wns_to_wes_bridge._build_narrative_delta` lines 133-152 never populates `npc_dialogue_since_last[]` or `wms_events_since_last[]` | Agent 9 | 8 of 8 tools | ~20 LOC | **P0 — ship first** |
| G03 | `[WNS-GAP]` | **`WMS_TRIGGER_FIRED` not published** — TriggerManager's `TriggerAction` stream is consumed by WMS interpreter only; WNS never sees milestones directly. Blocks the entire behavior-causal path. | Wave 4 | All behavior-causal content (esp. Skills, Titles, Hostiles, Quests) | ~10 LOC | **P0 — ship first** |
| G04 | `[WES-SCHEMA-GAP]` | **Bundle missing `trigger_archetype` + `behavior_signal`** — needed for behavior-causal dispatch + cross-archetype enrichment | Wave 4 | 8 of 8 tools | ~20 LOC + dataclass | **P0 — ship first** |
| G05 | Active bug | **Supervisor template references `${firing_address}` but variables dict doesn't populate it** — `LLMSupervisor.review` lines 130-143 | Agent 10 | Orchestrator-wide | 2 LOC fix | **P0 — ship first** |
| G06 | `[FRAGMENT-GAP]` | **`adjusted_instructions` rerun loop is one-way** — supervisor's adjustments not threaded into planner rerun. Today reruns are statistically the same plan. | Agent 10 | Orchestrator-wide | ~15 LOC + prompt | **P0 — ship first** |
| G07 | Missing infrastructure | **5 missing `reload()` methods** on Materials, Hostiles, Nodes, Skills, Titles databases | Materials, Hostiles, Nodes, Titles agents, pre-existing DESIGNER_LEDGER | 5 of 8 tools | ~50 LOC + 5 tests | **P0 — ship first** |
| G08 | Missing infrastructure | **`BehaviorInterpreter` module** — subscribes to `WMS_TRIGGER_FIRED`, decides dispatch-worthy, builds bundle, publishes `WNS_CALL_WES_REQUESTED` | Wave 4 | All behavior-causal content | New module ~300 LOC | P1 — behavior substrate |
| G09 | Missing infrastructure | **`CooldownArbiter`** — prevents back-to-back behavior-emergence on same player axis | Wave 4 | All behavior-causal content | New module ~50 LOC | P1 — behavior substrate |
| G10 | Missing infrastructure | **`behavior_dispatch_rules.json`** — designer-tunable per-tool behavior-threshold mapping | Wave 4 | All behavior-causal content | Designer config | P1 — behavior substrate |
| G11 | `[FRAGMENT-GAP]` | **Planner prompt: `trigger_archetype` discriminator + `scope_by_behavior_threshold` prose** | Wave 4 | Planner | Prompt edit + draft prose (Wave 4 §6.2) | P1 — behavior substrate |
| G12 | `[FRAGMENT-GAP]` | **Supervisor prompt: behavior-causal checks 7, 8, 9** (behavior-artifact fidelity, pool-gap rationality, cooldown respect) | Wave 4 | Supervisor | Prompt edit | P1 — behavior substrate |
| G13 | `[FRAGMENT-GAP]` | **Hub prompts: every hub reads `step.flavor_hints.behavior_inheritance` and propagates `${behavior_flavor}`** — DAG cascade flavor inheritance | Wave 4 | 8 of 8 hubs | Prompt edit ×8 + ~20 LOC | P1 — behavior substrate |
| G14 | `[FRAGMENT-GAP]` | **`StatStore.activity_profile(locality_id)` helper** — convenience accessor for per-locality discipline-mix dict | Wave 4 | All behavior-causal content | ~30 LOC | P1 — behavior substrate |
| G15 | Missing infrastructure | **`NPCDatabase.get_voice_excerpt(npc_id)` publish API** — exposes narrative + voice_anchor + personality + faction + home_chunk for downstream consumers | Agent 1 (Quests), Agent 6 (Skills), Agent 7 (Titles), Agent 2 (NPCs) | 6 of 8 tools | ~50 LOC + API design | P2 — hub feature |
| G16 | `[WES-SCHEMA-GAP]` | **Reverse cross-ref schema fields** — `granted_by_quest_id`, `taught_by_npc_id`, `hunted_by_quest_id`, `gather_quest_id`, `rewarded_by_quest_id` on titles/skills/hostiles/materials | Agent 1 + 2 + 3 + 4 + 6 + 7 | 5+ of 8 tools | Schema migration + tool prompts | P2 — hub feature |
| G17 | Active bug | **Materials category allow-list mismatch** — hub passes categories the tool's allow-list doesn't include; tool silently emits wrong category | Agent 4 | Materials | ~10 LOC fix | P2 — fix-as-you-touch |
| G18 | Active bug | **5 silent wiring failures in Nodes pipeline** — xref reads `materialId` but schema is `drops[]`; wrapper-key mismatch; missing reload; ID-candidates incomplete; respawn-map drops `"quick"` | Agent 5 | Nodes | ~30 LOC across 5 sites | P2 — fix-as-you-touch |
| G19 | Active bug | **`geoTypes` collision can suppress sacred biomes** — WES-generated geo_type with same key as sacred silently shadows | Agent 8 | Chunks | Namespace-check + ~15 LOC | P2 — fix-as-you-touch |
| G20 | Missing infrastructure | **Quest archive table** — `ArchivedQuest` with full metadata (duration, actual_result, actual_rewards, participating_npcs, tags, wns_thread_id) | Agent 1, per `quest_lifecycle_design.md` memory | Quests + WNS continuity | New module ~150 LOC + schema | P2 — hub feature |
| G21 | Missing infrastructure | **`prose_ambiguity_directive` shared prompt fragment** — included by every tool's system prompt | Wave 4 | 8 of 8 tools | Designer prose + 8 prompt edits | P3 — designer prose |
| G22 | Missing infrastructure | **Designer prose: `_game_context` WORLD TONE placeholder** — referenced in NL fragments but unset | Pre-existing, Designer Ledger | All WNS layers | Designer authoring | P3 — designer prose |
| G23 | Missing infrastructure | **Designer prose: per-layer voice for NL2-NL7** — current fragments are stub-stage | Pre-existing, Designer Ledger | All WNS layers | Designer authoring × 6 | P3 — designer prose |
| G24 | Missing infrastructure | **Designer prose: `scope_by_firing_tier` final version** — Agent 10 §8.3 has a v4 draft requiring designer review and playtest tuning | Agent 10 | Planner | Designer authoring | P3 — designer prose |
| G25 | Missing infrastructure | **Designer prose: per-purpose-per-layer firing guidance** — 48 cells (8 purposes × 6 NL layers) of when-to-fire prose in `_wes_tool` body | Agent 9 | All WNS layers | Designer authoring × 48 | P3 — designer prose |
| G26 | Missing infrastructure | **Designer config: `behavior_dispatch_rules.json` final content** — per-tool behavior thresholds, dispatch-worthy heuristics | Wave 4 | Behavior path | Designer config + tuning | P3 — designer prose |
| G27 | `[WES-SCHEMA-GAP]` | **`flavor_hints.behavior_inheritance` field** + RequestLayer propagation through cascade | Wave 4 §7.3 (chunks pseudo-trace DAG inheritance) | Chunks → nodes/hostiles/materials | ~15 LOC | P4 — DAG inheritance |
| G28 | Missing infrastructure | **WNS player-facing UI** — journal, event popups, world-state banners. Standalone narrative has no consumer surface today. | Agent 9 | Player-facing | New UI module | P5 — player UI |
| G29 | `[FRAGMENT-GAP]` | **Mixed-trigger arbiter** — deterministic decision on whether to merge concurrent narrative + behavior firings | Wave 4 | Orchestrator | New module ~100 LOC | P6 — mixed trigger polish |
| G30 | `[FRAGMENT-GAP]` | **`wns_player_presence_drift_detector`** — negative-pattern behavior trigger (locality affinity decay) | Wave 4 | WNS | Part of BehaviorInterpreter rule set | P6 — mixed trigger polish |
| G31 | `[WES-SCHEMA-GAP]` | **Cross-archetype enrichment** — populate `behavior_signal` (light slice) on narrative-causal firings too; populate narrative_context on behavior-causal firings | Wave 4 §7.2 | All firings | ~10 LOC | P6 — mixed trigger polish |
| G32 | `[FRAGMENT-GAP]` | **Supervisor reads `${tools_with_live_reload}`** — surface reload-pipeline state so supervisor refuses to commit content for a tool whose DB doesn't reload | Agent 10 | Supervisor | Prompt + ~10 LOC | Bundled with G07 |
| G33 | `[FRAGMENT-GAP]` | **Sacred-namespace registry summary to supervisor** — for sacred-shadowing detection | Agent 10 | Supervisor | Prompt + ~10 LOC | Bundled with G19 |
| G34 | `[FRAGMENT-GAP]` | **Plan log retention policy** — `llm_debug_logs/wes/<plan_id>/` accumulates indefinitely | Agent 10 | Operations | Config + ~20 LOC | Backlog |

**The pattern.** Twelve gaps cluster in the "ship first" P0 group (universal cross-cutting fixes + the load-bearing bugs). Seven gaps form the behavior-causal substrate (P1). Six form the hub-feature + fix-as-you-touch group (P2). Five are designer prose authoring (P3). The rest are progressive polish.

**Zero `[WMS-GAP]` rows.** The WMS substrate held under stringent review.

---

## 4. Shared infrastructure (concrete artifacts multiple features want)

Each item is a single concrete deliverable that, when built, serves multiple consumers. The personal-shopper principle made tangible: build once, share widely, divergence only where flavor genuinely demands it.

### 4.1 The bundle slice contract (post-fix)

**Owner:** WNS (bridge + assembler); WES (planner, slice, hubs).
**Consumers:** All 8 content tools, planner, supervisor.
**Where it lives:** `Game-1-modular/world_system/wes/context_bundle.py` (dataclass) + `Game-1-modular/world_system/wns/wns_to_wes_bridge.py` (assembler) + `Game-1-modular/world_system/wes/execution_planner.py` (`_bundle_to_vars`) + each hub's `_make_vars`.
**Sketch:** §2.2 above + `09-wns.md` §5.1 + `11-trigger-taxonomy.md` §5.7.
**Effort:** ~30 LOC across files + prompt fragment template variable additions.
**Leverage:** Universal. The single highest-leverage fix in the system.

### 4.2 The behavior-causal substrate

**Owner:** WNS (BehaviorInterpreter).
**Consumers:** All behavior-causal content (Skills, Titles, Hostiles, Quests primarily; Materials/Nodes/Chunks/NPCs secondarily).
**Components:**

- `BehaviorInterpreter` module at `Game-1-modular/world_system/wns/behavior_interpreter.py` — subscribes to `WMS_TRIGGER_FIRED`, implements `_is_dispatch_worthy`, builds `BehaviorSignal`, composes `<WES>` directive, publishes `WNS_CALL_WES_REQUESTED`.
- `CooldownArbiter` submodule — prevents back-to-back behavior dispatches on the same counter at the same address.
- `behavior_dispatch_rules.json` config — per-counter-category dispatch rules (which counters dispatch, which are journal-only, cooldown windows, per-tool eligibility).
- `WMS_TRIGGER_FIRED` event publication from `TriggerManager.on_event` to GameEventBus.
- `StatStore.activity_profile(locality_id)` helper.
- `BehaviorSignal` dataclass extension to `WESContextBundle`.

**Where it lives:** `world_system/wns/behavior_interpreter.py` + `world_memory/trigger_manager.py` (small event publish) + `world_memory/stat_store.py` (helper) + `world_system/wes/context_bundle.py` (BehaviorSignal field).
**Spec:** `11-trigger-taxonomy.md` §5.3 (BehaviorInterpreter), §5.4 (dispatch-worthy heuristics), §5.5 (per-layer eligibility), §5.7 (bundle extension).
**Effort:** ~450 LOC new + ~30 LOC edits + designer config authoring.
**Leverage:** Enables the behavior-causal trigger archetype entire. Without it, the unification thesis has only one path.

### 4.3 The NPC voice publish API

**Owner:** NPCs.
**Consumers:** Quests, Skills, Titles, Hostiles, dialogue speechbank, future modifier endpoints.
**API:** `NPCDatabase.get_voice_excerpt(npc_id: str) -> Dict[str, Any]` returning narrative + voice_anchor + personality + primary_faction + home_chunk + (post-archive) recent_quest_summary.
**Where it lives:** `Game-1-modular/data/databases/npc_db.py` extension.
**Effort:** ~50 LOC API + minor schema clarification on what's public vs. internal.
**Leverage:** 6 of 8 content tools, plus dialogue runtime.

### 4.4 Reverse cross-ref schema migrations

**Owner:** Schema (data models for each affected feature).
**Migrations needed:**

- Title: add `granted_by_quest_id: Optional[str]`, `granted_by_npc_id: Optional[str]`.
- Skill: add `taught_by_npc_id: Optional[str]`, `rewarded_by_quest_id: Optional[str]`.
- Hostile: add `hunted_by_quest_id: Optional[str]`.
- Material: add `gather_quest_id: Optional[str]`, `inherited_from_chunk_id: Optional[str]`.
- Node: add `inherited_from_chunk_id: Optional[str]`.
- NPC dynamic context: add `recent_quest_count: int`, `recent_quest_summaries: List[str]`.

**Where it lives:** `Game-1-modular/data/models/*.py` + each tool's schema validator.
**Effort:** ~5-10 LOC per model + corresponding tool prompt schema documentation.
**Leverage:** Cross-feature flavor cohesion. Each generated artifact knows the context that birthed it.

### 4.5 The `prose_ambiguity_directive` shared fragment

**Owner:** Cross-tool (single canonical fragment).
**Consumers:** All 8 content tools.
**Where it lives:** `Game-1-modular/world_system/config/prompt_fragments.json` with key `prose_ambiguity_directive`, included by every tool's system prompt.
**Content:** §2.6 above + `11-trigger-taxonomy.md` §8.4. Designer-authored acceptable/unacceptable patterns. Extra force when `trigger_archetype` is `"behavior"`.
**Effort:** Designer authoring + 8 prompt-include lines.
**Leverage:** All 8 tools simultaneously. Single principle, single fragment.

### 4.6 The 5 missing `reload()` methods

**Owner:** Data layer (each database singleton).
**Targets:** `MaterialDatabase`, `EnemyDatabase`, `ResourceNodeDatabase`, `SkillDatabase`, `TitleDatabase`.
**API per database:**

- `load_from_files(file_paths: List[Path])` — consolidates the per-database boot calls (esp. Materials' 7-call sequence in `game_engine.py:106-125`).
- `reload()` — re-reads sacred + overlays `*-generated-*.JSON` siblings, atomic swap.
- Publish `EVT_DATABASE_RELOADED(tool_name)` to GameEventBus on success.
- E2E test for each.

**Pre-existing pin** from DESIGNER_LEDGER. Confirmed by Agents 3, 4, 5, 7 independently.
**Effort:** ~50 LOC per database (≈250 total) + 5 E2E tests.
**Leverage:** 5 of 8 content tools. Without this, generated content silently degrades — the dispatcher publishes the reload event but nothing happens for these 5 databases.

### 4.7 The DAG flavor-inheritance plumbing

**Owner:** Planner (sets), RequestLayer (propagates), Hubs (read).
**Components:**

- `flavor_hints.behavior_inheritance: Optional[str]` field on plan steps.
- Planner: when emitting a mixed-trigger chunk plan, attaches `behavior_inheritance = "alchemy"` (or analogous) to downstream hostile + node + material specs.
- RequestLayer.build_specs: when requesting payload carries `behavior_inheritance`, propagates to cascade spec's `flavor_hints`.
- Every hub's `_make_vars` reads it and exposes as `${behavior_flavor}` template variable.

**Spec:** `11-trigger-taxonomy.md` §7.3.
**Where it lives:** `world_system/wes/execution_planner.py` + `world_system/wes/request_layer.py` + each hub.
**Effort:** ~15 LOC + prompt updates × 8.
**Leverage:** Chunks + downstream cascade. The Chunks mixed-trigger case is the unification thesis at its most concrete.

### 4.8 The supervisor template fix + adjusted-instructions threading

**Owner:** Orchestration.
**Components:**

- Fix `${firing_address}` population in `LLMSupervisor.review` (G05 — active bug).
- Thread `adjusted_instructions` from supervisor verdict into planner rerun loop (G06).
- Supervisor reads `${tools_with_live_reload}` to refuse commits for non-reloading tools (G32).
- Supervisor reads sacred-namespace summary for sacred-shadowing detection (G33).

**Where it lives:** `world_system/wes/supervisor.py` + planner rerun path.
**Effort:** ~30 LOC across changes.
**Leverage:** Supervisor reliability across all 8 tools.

---

## 5. Designer action queue (prose authoring)

Designer prose is its own phase because the trace pass surfaced a lot of it, and prose authoring runs serially with playtest feedback. Wave 4's prose-ambiguity principle applies here: the designer's authoring should anchor in feel, not enumerate the mechanic.

| # | Item | Source | Estimate | Notes |
|---|---|---|---|---|
| D1 | `_game_context` WORLD TONE | Pre-existing pin | 1-2 hours | Single block; sets tone for all WNS layers. The user's "what does this world feel like" answer. |
| D2 | Per-layer NL voice (NL2-NL7) | Agent 9, pre-existing pin | 4-8 hours × 6 layers | Current fragments are placeholder. Designer authoring: "what does NL2 sound like vs NL7." |
| D3 | `scope_by_firing_tier` v4 prose (designer pass) | Agent 10 §8.3 | 2-4 hours + playtest | Agent 10 produced a strong draft; designer reviews + tunes against playtest abandonment rates. |
| D4 | `scope_by_behavior_threshold` v4 prose | Wave 4 §6.2 | 2-4 hours + playtest | Wave 4 produced a draft; designer reviews + tunes. |
| D5 | `prose_ambiguity_directive` shared fragment | Wave 4 §8.4 | 1-2 hours | Acceptable/unacceptable patterns per the user's correction. |
| D6 | Per-layer voice + per-purpose shape (14 modular blocks, runtime-composed) | Agent 9 §6.3, user refinement 2026-06-02 | 30-45 min × 14 blocks (~7-10 hours) | **Architectural correction.** Author 6 layer-voice blocks (one per NL2-NL7: voice, narrative scale) + 8 purpose-shape blocks (one per WES purpose: directive constraints). Weaver assembles at runtime via tag-indexed composition (same pattern as WMS/WNS prompt fragments per memory `feedback_wns_prompts_must_be_tag_indexed.md`). Replaces the agents' originally-proposed 48-cell matrix — flat enumeration was the wrong shape; modularity is the right one. |
| D7 | `behavior_dispatch_rules.json` | Wave 4 §5.4 | 4-8 hours + playtest | Per-counter dispatch rules; cooldown windows; per-tool eligibility. Includes NPC manifestation rules (§2.7). |
| D8 | Per-tool prose patterns (acceptable/unacceptable) | Wave 4 §8.2 | 1-2 hours × 8 tools | Optional supplementation of D5 with tool-specific examples. |

**Total designer time:** roughly 12-25 hours of authoring work, spread across the build phases. Some items (D1, D2, D5) are blocking for content generation quality; others (D3, D4, D7) require playtest feedback loops. (Reduced from initial 30-50 hour estimate after the D6 modularity correction.)

The designer is the user. This queue is what the user must produce (or approve, if I draft).

---

## 6. Build sequence (8 phases with ship-criteria)

The build plan is sequenced so each phase ships with concrete, observable success criteria. Phases are dependency-ordered: earlier phases enable later phases. Within a phase, tasks can be parallelized.

The phasing honors the user's directive to avoid `wes_tool_recipes` and `wes_tool_equipment` (handled by the existing crafting LLM in `systems/llm_item_generator.py` + `systems/crafting_classifier.py`). All work targets the 27 in-scope WNS/WES LLM tasks plus the deterministic infrastructure.

### Phase 0 — Plumbing (low-risk, high-leverage)

**Scope:** Active bugs + missing infrastructure where the fix is mechanical.

**Tasks:**

- G05 — supervisor template `${firing_address}` populate fix (2 LOC)
- G06 — `adjusted_instructions` threading into planner rerun (~15 LOC + prompt edit)
- G07 — 5 missing `reload()` methods + `load_from_files` consolidation + EVT publish + 5 E2E tests
- G02 — bridge populates `npc_dialogue_since_last` and `wms_events_since_last`
- G03 — `WMS_TRIGGER_FIRED` event publication from TriggerManager
- G14 — `StatStore.activity_profile(locality_id)` helper
- G17, G18, G19 — Materials category fix + Nodes wiring failures + Chunks geoTypes namespace check

**Ship criteria:**

- All 8 content databases swap content on `EVT_DATABASE_RELOADED` signal (test: write a generated material, fire reload, query DB, find material).
- Supervisor's `${firing_address}` is populated in every rerun (test: trigger supervisor failure, check prompt content includes the address).
- Supervisor's `adjusted_instructions` reach the planner rerun (test: failure → rerun, planner prompt shows prior feedback).
- WMS publishes `WMS_TRIGGER_FIRED` to bus when thresholds cross (test: subscribe a probe, trip a counter, observe).
- Nodes, Materials, Chunks pre-existing wiring failures fixed (each has its own integration test).

**Effort:** ~300 LOC + 5 E2E tests + 3 integration tests.
**Duration estimate:** 1-2 working days.
**Unblocks:** Phase 1, Phase 2.

### Phase 1 — Bundle contract (the universal cross-cutting fix)

**Scope:** Build the post-fix bundle slice that closes the narrative-disconnection failure across all 8 content tools.

**Tasks:**

- G01 — `BundleToolSlice` extensions (firing_layer_summary, parent_summaries, geographic_chain, threads_in_focal_address full payloads, threads_in_parent_addresses, wms_events_since_last)
- G04 — `trigger_archetype` field + `BehaviorSignal` dataclass on bundle (extension to G01)
- Each hub's `_make_vars` extended to expose new template variables (`${firing_narrative}`, `${parent_narratives}`, `${geographic_chain}`, `${thread_fragments}`, `${parent_thread_fragments}`, `${wms_events_summary}`, `${behavior_flavor}`)
- Planner's `_bundle_to_vars` extended same
- Designer review of new template variable usage in planner + each hub's user template

**Ship criteria:**

- Every WES content tool receives the new bundle fields (test: fire a directive, log tool input, verify presence).
- A test bundle with `parent_summaries` populated shows them rendered in the tool's prompt (sanity-check rendering).
- All 8 tools' system prompts updated to acknowledge new fields exist.
- Existing tests pass.
- Round-trip smoketest (`tools/wes_real_llm_smoketest.py`) shows narrative-aware output where it previously produced narrative-blind output.

**Effort:** ~30 LOC code + 8 prompt edits + designer review.
**Duration estimate:** 1 working day code + 1 day designer prompt review.
**Unblocks:** Phase 2 (behavior signal field is here), Phase 4 (hubs reading reverse cross-refs).

### Phase 2 — Behavior-causal substrate

**Scope:** Build the entire behavior-causal trigger archetype.

**Tasks:**

- G08 — `BehaviorInterpreter` module
- G09 — `CooldownArbiter` submodule
- G10 — `behavior_dispatch_rules.json` (Phase 3 designer authoring; for now: skeleton + dev-time rules)
- G11 — planner prompt: `trigger_archetype` discriminator + `scope_by_behavior_threshold` prose (Wave 4 draft)
- G12 — supervisor prompt: behavior-causal checks 7, 8, 9
- G13 — each hub's prompt: read `${behavior_flavor}` (DAG inheritance; bundles into Phase 5 too)
- G31 — cross-archetype enrichment (behavior_signal populated on narrative-causal too, light slice)

**Ship criteria:**

- The user's potions example works end-to-end: simulate 1,000 `item_used` events for potion at a locality, observe `WMS_TRIGGER_FIRED` → BehaviorInterpreter dispatch decision → bundle with `trigger_archetype="behavior"` → planner emits skill plan → skill tool generates an instant-heal skill with `unlockMethod: BehaviorEmergence` and no NPC teacher.
- Cooldown: re-simulate immediately; BehaviorInterpreter suppresses (cooldown active).
- Cross-archetype enrichment: a narrative-causal firing at the same locality now shows `behavior_signal.activity_profile` populated (light slice).
- Supervisor passes the behavior-causal content with checks 7, 8, 9 active.

**Effort:** ~500 LOC new code + ~20 LOC integration + prompt edits + integration tests.
**Duration estimate:** 3-5 working days code + 1-2 days integration testing.
**Unblocks:** Phase 5 (DAG inheritance needs behavior_flavor in place).

### Phase 3 — Designer prose authoring (CEO-style)

**Scope:** Author the prose that gives the system taste.

**Tasks:**

- D1 — `_game_context` WORLD TONE
- D2 — Per-layer NL voice (NL2-NL7)
- D3 — `scope_by_firing_tier` v4 final prose
- D4 — `scope_by_behavior_threshold` v4 final prose
- D5 — `prose_ambiguity_directive` shared fragment
- D6 — Per-layer voice (6 blocks for NL2-NL7) + per-purpose shape (8 blocks for the 8 WES purposes) — 14 modular blocks total, composed at weaver runtime
- D7 — `behavior_dispatch_rules.json` content (including NPC manifestation rules)
- D8 — Per-tool acceptable/unacceptable prose patterns

**Ship criteria:**

- Prompt Studio simulator round-trips produce designer-acceptable output for any layer × purpose combination at assembly time.
- Manual playtest at NL2 shows village-gossip voice; NL7 shows chronicler-of-ages voice; both distinguishable.
- Prose-ambiguity sample run: trigger a behavior-causal skill; the resulting skill's `evolution.requirement` reads "Master its usage in the native environment" or analogous (not "Use 100 times").
- A behavior-causal NPC firing manifests an NPC framed as already-existing ("the moors-master who has watched the player"), not as newly-invented ("a new person has appeared").

**Effort:** 12-25 hours designer time, parallelizable.
**Duration estimate:** 3-7 days designer time, can overlap with Phase 4 + Phase 5 code work.
**Unblocks:** Quality bar for all generated content (the trace work covered the structure; designer prose covers the soul).

### Phase 4 — NPC hub API + cross-ref schema migrations

**Scope:** Build the hub feature pattern and migrate schemas for reverse cross-refs.

**Tasks:**

- G15 — `NPCDatabase.get_voice_excerpt()` publish API
- G16 — schema migrations for `granted_by_quest_id`, `taught_by_npc_id`, `hunted_by_quest_id`, `gather_quest_id`, etc.
- Each hub's `_make_vars` reads reverse cross-refs from the spec and exposes them
- Each tool's prompt acknowledges reverse cross-refs and flavors output accordingly

**Ship criteria:**

- A quest emitted in plan P references NPC giver N; quest tool's input includes N's voice_excerpt; quest's `completion_dialogue` rhymes with N's voice.
- A title generated with `granted_by_quest_id: Q` references Q's theme in its narrative.
- A skill generated with `taught_by_npc_id: N` references N's lineage in its narrative.

**Effort:** ~100 LOC API + schema migrations × 6 + prompt updates × 6.
**Duration estimate:** 2-3 working days.
**Unblocks:** Quality compounding — content references the content that birthed it.

### Phase 5 — DAG behavior-inheritance

**Scope:** Make the user's chunks pseudo-trace work end-to-end. Mixed-trigger chunk firing propagates behavior flavor down to nodes, hostiles, materials.

**Tasks:**

- G27 — `flavor_hints.behavior_inheritance` field on plan steps
- RequestLayer propagation through cascade
- Each hub reads and exposes `${behavior_flavor}`
- Tool prompts acknowledge: "If `${behavior_flavor}` is set, tilt this output toward that discipline/style. Subtle — not theme park, but a flavor."

**Ship criteria:**

- Simulate mixed-trigger chunks firing (NPC rumors of new terrain + chunks_seen milestone + heavy alchemy activity). Result: chunk template + 1-2 nodes + 1-2 hostiles + 1-2 materials, all alchemy-tilted, all narratively coherent.
- The propagation log shows `behavior_inheritance` flowing from chunk → cascade → downstream tools.

**Effort:** ~50 LOC + prompt updates × 8.
**Duration estimate:** 2-3 working days.
**Unblocks:** The unification thesis at its most concrete. The world's response to player identity flows through an entire generated ecosystem.

### Phase 6 — WNS player surface (minimal / optional, per user direction 2026-06-02)

**Scope decision.** Per user: "The WNS should actually be relatively understated as a portion of the game. I am not sure I will let the player see it at all." The WNS is internal substrate that flavors generated content; the player experiences the world's response through the *content* itself (new skills, NPCs, hostiles, quests, materials, chunks), not by reading the chronicle directly.

**Implication.** Phase 6 collapses to optional debug/designer tooling. The standalone-narrative deliverable from Agent 9 §1.4 was theoretical; if the player never sees it, what was always actually shipping was the *flavoring of generated content* — which Phases 1-5 cover entirely.

**Tasks (all optional, designer-facing only):**

- (Optional) Internal event-log UI overlay (extends existing F12 overlay) — shows recent WNS firings for designer/debug inspection only. May reuse existing observability buffer.
- (Optional) Prompt Studio surface showing the WNS narrative store at the locality the designer is inspecting. Useful for tuning prose-ambiguity directive sufficiency.
- Supervisor-failure-retraction handling: deferred entirely (no player-visible WNS narrative to retract).

**Ship criteria (only if Phase 6 ships at all):**

- Designer can inspect recent WNS narrative firings in Prompt Studio or via F12 overlay.
- No player-facing UI surfaces the WNS narrative.

**Effort:** 0-100 LOC if any work happens here; can defer to v4.5 or later if no designer-tooling need surfaces during Phases 0-5.
**Duration estimate:** 0-1 working day, *if any*.
**Unblocks:** Nothing critical — Phases 1-5 deliver the full player experience without this.

### Phase 7 — Mixed-trigger arbiter + drift detector + quest archive

**Scope:** Address the remaining behavior-causal polish: concurrent firings, negative-pattern triggers. Quest archive lands here as a separate substrate.

**Tasks:**

- G29 — `wns_mixed_trigger_arbiter` (deterministic) — when narrative + behavior want a firing in the same window at the same address, decide merge vs. separate
- G30 — `wns_player_presence_drift_detector` — player absence from a locality triggers WNS narrative shift
- G20 — **Quest archive substrate** (per user direction 2026-06-02): the archive lives as a separate database (`QuestArchiveDatabase` or analogous), NOT as a WMS extension. WMS continues to see quest *facts* via existing event types (`quest_accepted`, `quest_completed`, `quest_failed`) and L2 evaluators (`social_quests` aggregations like "10 quests with X tag"). The archive holds *prose history* — duration, actual_result, participating_npcs, archived_narrative_tags, wns_thread_id — and exposes read methods via `WorldQuery` so WNS chroniclers and WES tools can pull from it when narratively relevant. Clean separation: WMS = events; archive = narratives.

**Ship criteria:**

- A concurrent narrative + behavior firing produces ONE merged plan (or the rejection rationale is logged).
- Player avoids Tarmouth for 10 game-days; WNS fires a behavior-causal "Tarmouth has not seen the wanderer in two seasons" entry (negative-pattern trigger).
- Quest archive populates on turn-in; WNS chronicler at the originating district can reference past quest deeds via `WorldQuery.recent_archived_quests(address, tag_filter)`.
- WMS sees quest facts but does NOT carry archive prose rows.

**Effort:** ~300 LOC + prompts.
**Duration estimate:** 3-5 working days.
**Unblocks:** Operating-pace polish; mixed-trigger handling becomes reliable; negative-pattern behavior triggers join the substrate.

### Phase summary

| Phase | Duration estimate | Unlocks |
|---|---|---|
| 0 — Plumbing | 1-2 days | Phase 1, Phase 2 |
| 1 — Bundle contract | 1 day code + 1 day prompt review | Universal cross-cutting fix; Phase 2 enabled |
| 2 — Behavior substrate | 3-5 days code + 1-2 days integration | Behavior-causal path live; user's potions example works |
| 3 — Designer prose | 3-7 days designer time (overlaps with later phases) | Quality bar across all content |
| 4 — NPC hub + cross-refs | 2-3 days | Content references content; manifestation framing wired |
| 5 — DAG inheritance | 2-3 days | Mixed-trigger chunks work; user's chunks example works |
| 6 — WNS player surface | 0-1 day (optional, may defer entirely) | Designer-facing only; no player UI shipped |
| 7 — Mixed-trigger polish + quest archive | 3-5 days | Negative-pattern triggers + concurrent firings + quest archive as separate substrate |

**Total code estimate:** roughly 20-30 working days. (Reduced from 25-35 estimate as Phase 6 collapses.)
**Total designer estimate:** 12-25 hours (3-7 days, parallelizable). (Reduced from 30-50 hour estimate after D6 modularity correction.)

These are estimates against the spec; reality compresses or expands per actual code surfaces.

---

## 7. Risk register

Where the assumptions could break and what to watch for.

### 7.1 The WMS-sufficient assumption

**Risk.** Eleven traces raised zero `[WMS-GAP]` markers. The discipline held under the methodology. But every trace is theoretical; the WMS hasn't been hit at the rates the behavior-causal path implies. When `TriggerManager` is publishing dozens of `WMS_TRIGGER_FIRED` events per minute at scale, the assumed-reachable signals (cross-session deltas, per-locality activity profiles, trajectory queries) may have query-cost issues that the trace pass didn't surface.

**Mitigation.** Phase 0 ships `WMS_TRIGGER_FIRED` publication early. Phase 2 ships the BehaviorInterpreter. Instrument both. Measure query cost per dispatch decision. If hot-path query cost is high, add caching or denormalize specific signals. Treat as `[WMS-ENHANCEMENT]` (deferred future capability) rather than `[WMS-GAP]`.

### 7.2 Prose ambiguity vs. determinism — where's the line?

**Risk.** The prose-ambiguity directive is a feature for player-facing prose. But the planner's `step.intent` is prose-structural hybrid (Agent 10 §8 noted this) — the hub parses it. If the directive overcorrects into the planner's intent prose, the hubs lose specificity.

**Mitigation.** §2.6 distinguishes structural from prose fields explicitly. The directive applies to prose fields specifically. The planner's `step.intent` is the boundary case — keep it specific enough for hub parsing, evocative enough for downstream prose to inherit feel. Designer review during Phase 3 should explicitly check intent prose against this distinction.

### 7.3 Pre-generated quest pool sizing

**Risk.** Agent 1 recommended a minimum of 3 quests per active giver. If pool runs dry mid-session and cascade can't refill fast enough, the player notices "no quests available." If pool oversizes, the WNS narrative moves on and pool quests stale.

**Mitigation.** Phase 7's quest archive + stale-quest modifier (the user mentioned this idea in the original quest example) is the long-term fix. Short-term: instrument pool size per giver in WES observability overlay; tune pool floor based on playtest data. If staleness becomes a problem in playtest, accelerate Phase 7's modifier endpoint.

### 7.4 BehaviorInterpreter dispatch-worthy heuristics

**Risk.** Wave 4 §5.4 sketched heuristics (suppress low-significance counters, cooldown, transit-detection, allow milestone rungs at 100+, etc.). These are designer-tunable but untested. If too permissive: player buried in new content. If too strict: behavior path silent, unification thesis falls apart.

**Mitigation.** Phase 2 ships dev-time rules; Phase 3 designer authors final `behavior_dispatch_rules.json`. Instrument BehaviorInterpreter — log every threshold event, every dispatch decision, every suppression reason. Tune based on observed cadence. Target: 10-20% of threshold events dispatch; 80-90% are journal-only or suppressed.

### 7.5 Cascade cost with behavior-inheritance

**Risk.** Phase 5's DAG flavor inheritance means chunk firings produce 1 chunk + downstream cascades for nodes + hostiles + materials, all flavor-aware. This is more cascade depth than narrative-causal chunks. If cascade depth exceeds `MAX_RUNTIME_CASCADE_DEPTH`, content emits incomplete.

**Mitigation.** Measure cascade depth in Phase 5 integration tests. If frequently hitting the cap, raise the cap for mixed-trigger chunks specifically OR push the inheritance into specific tools as flavor hints rather than full cascade specs. The current cap is conservative; chunks-with-inheritance is the legitimate exception.

### 7.6 Designer prose authoring throughput

**Risk.** Phase 3 needs ~30-50 hours of designer time. Designer is the user. If the user can't sustain that pace, prose phases delay code phases or code phases ship without designer prose (using stubs).

**Mitigation.** Phases are sequenced so code ships with prose stubs. Designer authoring is fully parallelizable; can happen during code phases. The 48-cell per-purpose-per-layer matrix can be batched per-purpose (8 batches of 6 cells each), which is more practical than 48 separate authoring sessions.

### 7.7 The 9-rung discipline at scale

**Risk.** Eleven agents walked the rungs successfully. But future content additions (new content types, new behavior signals, new trigger patterns) won't have the formal pass. Without the discipline, the WMS-sufficient assumption erodes.

**Mitigation.** Add a `[WMS-GAP]` review gate to the build process. Any PR that introduces a `[WMS-GAP]` requires the 9-rung walk in the PR description. The discipline becomes a code-review checklist, not just a trace-time exercise.

---

## 8. Open questions — RESOLVED 2026-06-02

The original four big questions are now closed; resolutions captured here. The smaller three (5, 6, 7 from earlier draft) are bundled into the resolutions or have clear leans.

### 8.1 RESOLVED — Phase 6 WNS player surface

**Decision:** Minimal / possibly invisible. The WNS is internal substrate that flavors generated content; the player experiences the world's response through the *content* itself, not by reading the chronicle directly. Phase 6 collapses to optional designer/debug tooling. The standalone-narrative deliverable from Agent 9 was theoretical; what was always actually shipping was the *flavoring of generated content* in Phases 1-5.

User's words: *"The WNS should actually be relatively understated as a portion of the game. I am not sure I will let the player see it at all."*

### 8.2 RESOLVED — Quest archive as separate substrate

**Decision:** Archive lives outside WMS as `QuestArchiveDatabase` (or analogous singleton). The WMS continues to see quest *facts* via existing event types (`quest_accepted`, `quest_completed`, `quest_failed`) and L2 evaluators (`social_quests` aggregations like "10 quests with X tag"). The archive holds *prose history* (duration, actual_result, participating_npcs, archived_narrative_tags, wns_thread_id) and is queryable by WNS chroniclers and WES tools via `WorldQuery` when narratively relevant. Clean separation: **WMS = events; archive = narratives.**

User's words: *"the WMS might see something like 10 quests with a XX tag. The WMS is events remember not narratives. But the WNS or WES should be able to see it as their context when relevant."*

This avoids violating the §2.8 "WMS is sufficient" stringency commitment — the archive is not a WMS structural change; it's a sibling substrate.

### 8.3 RESOLVED — D6 modularity correction (the 14-block authoring)

**Decision:** Replace the 48-cell matrix with 14 modular blocks: 6 layer-voice blocks (one per NL2-NL7) + 8 purpose-shape blocks (one per WES purpose). Weaver assembles at runtime via tag-indexed composition — same pattern as WMS/WNS prompt fragments. The 48-cell matrix the agents proposed was flat enumeration; modularity is structurally consistent with the rest of the prompt-architecture commitment.

User's words: *"I would write one for each layer and then one for each WES purpose. Then simply table them after a sanity check. This drives home the modularity that is expected."*

Practical impact: designer effort drops from 50-90 hours to 7-10 hours for D6 alone. Phase 3 total designer time drops to 12-25 hours.

### 8.4 RESOLVED — NPC manifestation framing

**Decision:** Behavior-causal triggers DO dispatch `new-npc` directives, but the prompt-design discipline frames the manifestation as "the person who has always existed narratively and whom the player's behavior has now brought them into proximity with" — not "a new person is invented now." The king has always been king; the master fletcher of the moors has always been there; the WES tool just hadn't authored their JSON until the player's milestone-crossing created a context where meeting would plausibly happen.

User's words: *"a king might always narratively exist but we wouldn't make them until the player had a chance of meeting them at all."*

This promotes NPCs from "low behavior-causal weight" to mid-high in the Wave 4 §4.7 audit. The manifestation framing becomes a specific clause in the `behavior_dispatch_rules.json` content and the NPC tool's system prompt.

### 8.5 Minor / bundled questions (carried over from earlier draft)

- **`scope_by_behavior_threshold` playtest cycle** — parallel with `scope_by_firing_tier` tuning, both during Phase 3 designer prose authoring. No strong scheduling concern.
- **Supervisor failures retracting WNS narrative** — deferred entirely now that 8.1 has the WNS staying invisible to the player. No consumer surface means no retraction need.
- **Mixed-trigger arbiter — deterministic** — confirmed deterministic per Wave 4 §9.3.

---

## 9. Explicitly OUT of scope

The user's hard constraints are honored throughout:

- **`wes_tool_recipes`** — DOES NOT EXIST. Recipe discovery is player-driven via the existing `systems/llm_item_generator.py` + `systems/crafting_classifier.py` invented-items pipeline (shipped Jan 2026). New materials feed that existing system; the WES tool universe does NOT include recipes.

- **`wes_tool_equipment`** — same as recipes. Equipment generation happens through the crafting LLM, not WNS→WES.

- **WMS structural changes** — the substrate is sufficient. Creative extraction (the 9-rung discipline) is the rule. WMS enhancements (deferred future capability) may be backlog-tracked but no WMS changes block any phase.

- **New content endpoints generally** — the WES content tool universe is FIXED at the existing 8. Speculative endpoints that surfaced (`wes_quest_modifier`, `wes_quest_giver_curator`, `wes_thread_summarizer`, `wes_orphan_classifier`, etc.) are explicitly speculative and live in each trace's section 9. None are promoted to required by the build plan.

- **Re-litigating settled architectural decisions** — the WMS / WNS / WES three-system topology, tag-indexed prompt assembly, content registry shape, atomic swap with sacred files untouched, cascade-by-N triggering. These are binding.

---

## 10. How to use this document

For the user (the project owner who reads this to decide what to build next):

- **Read Section 2 first.** The eight architectural conclusions are the load-bearing design decisions. If any disagree with your taste, the build plan needs revision.
- **Skim Section 3.** The gap inventory is sortable by leverage. The P0 fixes are the universal cross-cutting ones.
- **Decide on Section 8.** The seven open questions are yours to resolve.
- **Use Section 6 as the working plan.** The 8-phase sequence is the dependency-ordered roadmap.

For a future implementer agent picking up the build (or me, after `/compact`):

- Read in order: this document → `11-trigger-taxonomy.md` (the unification frame) → `01-quests.md` (the calibrator) → the trace for the feature you're touching.
- When touching the planner / supervisor / request layer, read `10-orchestration.md`.
- When touching the bundle / `NarrativeDelta` / WNS prompt assembly, read `09-wns.md`.
- When designing behavior-causal content for a specific tool, read `11-trigger-taxonomy.md` §4.X for that tool's audit.

For the specific build phases:

| Working on | Primary references |
|---|---|
| Phase 0 plumbing | DESIGNER_LEDGER + this doc §6 + each affected trace's gap section |
| Phase 1 bundle | `09-wns.md` §5 + `11-trigger-taxonomy.md` §5.7 |
| Phase 2 behavior substrate | `11-trigger-taxonomy.md` (the entire trace) |
| Phase 3 designer prose | This doc §5 + per-trace section 8 (prose-ambiguity sweep) + Agent 10 §8 |
| Phase 4 NPC hub | `02-npcs.md` (full trace) + `01-quests.md` §6.4 recommendations |
| Phase 5 DAG inheritance | `11-trigger-taxonomy.md` §7.3 + `08-chunks.md` |
| Phase 6 player UI | `09-wns.md` Part A (sections 1-3) |
| Phase 7 mixed-trigger polish | `11-trigger-taxonomy.md` §9 + `01-quests.md` §9 (quest archive) |

The methodology that produced the traces is documented in `C:\Users\vipVi\.claude\projects\c--Users-vipVi-PycharmProjects-Game-1\memory\next_task_wns_wes_backwards_design.md`. The user's mentality reminders, the 9-rung WMS checklist, the gap-marker taxonomy — all there.

---

## Appendix A — The 11 traces

| File | Anchor | Wave | Status |
|---|---|---|---|
| `01-quests.md` | Quest JSON | 1 (REFERENCE) | Complete |
| `02-npcs.md` | NPC JSON + dialogue speechbank | 2 | Complete |
| `03-hostiles.md` | Hostile JSON | 2 | Complete |
| `04-materials.md` | Material JSON | 2 | Complete |
| `05-nodes.md` | Resource node JSON | 2 | Complete |
| `06-skills.md` | Skill JSON | 2 | Complete |
| `07-titles.md` | Title JSON | 2 | Complete |
| `08-chunks.md` | Chunk template JSON | 2 | Complete |
| `09-wns.md` | WNS narrative + WNS-to-WES contract | 2 | Complete |
| `10-orchestration.md` | Planner / Supervisor / RequestLayer decisions | 3 | Complete |
| `11-trigger-taxonomy.md` | Cross-cutting trigger archetype framework | 4 (meta) | Complete |

## Appendix B — Gap marker reference

| Marker | Severity | When to use |
|---|---|---|
| `[FRAGMENT-GAP]` | Liberal | Prompt fragment shape wrong or missing template variable |
| `[WNS-GAP]` | Liberal | WNS bundle / bridge / schema missing capability |
| `[WES-SCHEMA-GAP]` | Liberal | WES dataclass / slice / schema can't carry needed field |
| `[WMS-ENHANCEMENT]` | Deferred | Would make WMS extraction easier; not blocking |
| `[WMS-GAP]` | **STRINGENT** | 9-rung checklist required; ZERO raised across 11 agents |

## Appendix C — Methodology pointers

Primary memory entries (in `C:\Users\vipVi\.claude\projects\c--Users-vipVi-PycharmProjects-Game-1\memory\`):

- `next_task_wns_wes_backwards_design.md` — the methodology + 9-rung checklist + agent dispatch plan
- `feedback_designer_ledger_walkthrough_procedure.md` — the 3-part presentation procedure
- `wms_vs_wns_voice_distinction.md` — WMS = factual chronicle; WNS = literary embroidery
- `feedback_wns_prompts_must_be_tag_indexed.md` — prompt architecture
- `hub_dependency_resolution.md` — orphan detection, reactive hub triggering
- `quest_lifecycle_design.md` — quest archive design
- `npc_schema_overhaul_v3.md` — NPC v3 schema split (static + dynamic context)
- `tag_system_functionality.md` — tag library discipline
- `chunk_evolution_future_idea.md` — speculative post-release chunk evolution
- `wns_affinity_modifier_tool.md` — deterministic AffinityShift directives

Working docs (in `Development-Plan/`):

- `WORLD_SYSTEM_WORKING_DOC.md` — v4 canonical architecture (still in original prose; CEO-style rewrite pinned for after this pass)
- `DESIGNER_LEDGER.md` — current build state, plain English

---

*End of consolidation.*

*The trace pass was structurally complete on 2026-06-02. The build plan is now actionable. The next step is the user's: approve the phasing, decide on the seven open questions, then begin Phase 0.*
